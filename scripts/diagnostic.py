#!/usr/bin/env python3
"""
AGORA System Diagnostic - End-to-End Testing Pre-Check

Checks what can be run without Docker and provides installation guidance.
"""

import os
import sys
import subprocess
from pathlib import Path

# ANSI colors
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(text):
    print(f"\n{BOLD}{BLUE}{'=' * 80}{RESET}")
    print(f"{BOLD}{BLUE}{text:^80}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 80}{RESET}\n")

def check_command(cmd, name):
    """Check if a command exists."""
    try:
        result = subprocess.run(
            ['which', cmd],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            print(f"{GREEN}✓{RESET} {name}: {result.stdout.strip()}")
            return True
        else:
            print(f"{RED}✗{RESET} {name}: Not found")
            return False
    except Exception as e:
        print(f"{RED}✗{RESET} {name}: Error checking - {e}")
        return False

def check_docker():
    """Check Docker installation and status."""
    print(f"\n{BOLD}Docker Status:{RESET}")
    
    # Check if docker command exists
    docker_installed = check_command('docker', 'Docker CLI')
    
    if not docker_installed:
        print(f"\n{YELLOW}⚠{RESET}  Docker is required but not installed.")
        print(f"\n{BOLD}Installation Guide:{RESET}")
        print("1. Download Docker Desktop from: https://www.docker.com/products/docker-desktop")
        print("2. Or install via Homebrew: brew install --cask docker")
        print("3. Start Docker Desktop application")
        print("4. Verify: docker --version")
        return False
    
    # Check if Docker daemon is running
    try:
        result = subprocess.run(
            ['docker', 'info'],
            capture_output=True,
            text=True,
            check=False,
            timeout=5
        )
        if result.returncode == 0:
            print(f"{GREEN}✓{RESET} Docker daemon is running")
            return True
        else:
            print(f"{YELLOW}⚠{RESET}  Docker is installed but daemon is not running")
            print(f"   Start Docker Desktop application")
            return False
    except subprocess.TimeoutExpired:
        print(f"{YELLOW}⚠{RESET}  Docker daemon not responding (timeout)")
        return False
    except Exception as e:
        print(f"{RED}✗{RESET} Error checking Docker daemon: {e}")
        return False

def check_python_env():
    """Check Python environment and dependencies."""
    print(f"\n{BOLD}Python Environment:{RESET}")
    
    # Python version
    version = sys.version.split()[0]
    print(f"{GREEN}✓{RESET} Python: {version}")
    
    # Check key packages
    packages = {
        'sqlalchemy': 'Database ORM',
        'fastapi': 'Core API framework',
        'temporalio': 'Workflow engine client',
        'pytest': 'Testing framework'
    }
    
    missing_packages = []
    for package, description in packages.items():
        try:
            __import__(package)
            print(f"{GREEN}✓{RESET} {description} ({package})")
        except ImportError:
            print(f"{YELLOW}⚠{RESET}  {description} ({package}) - not installed")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n{YELLOW}Install missing packages with:{RESET}")
        print(f"  cd packages/db && pip3 install -r requirements.txt -r requirements-test.txt")
        print(f"  cd apps/core-api && pip3 install -r requirements.txt")
        print(f"  cd apps/worker && pip3 install -r requirements.txt")
    
    return len(missing_packages) == 0

def check_project_structure():
    """Verify AGORA project structure."""
    print(f"\n{BOLD}Project Structure:{RESET}")
    
    project_root = Path.cwd()
    required_dirs = [
        'apps/core-api',
        'apps/worker',
        'apps/web',
        'packages/db',
        'tests',
        'scripts',
        'infra'
    ]
    
    all_exist = True
    for dir_path in required_dirs:
        full_path = project_root / dir_path
        if full_path.exists():
            print(f"{GREEN}✓{RESET} {dir_path}/")
        else:
            print(f"{RED}✗{RESET} {dir_path}/ - MISSING")
            all_exist = False
    
    return all_exist

def check_infrastructure_services():
    """Check if infrastructure services are running."""
    print(f"\n{BOLD}Infrastructure Services:{RESET}")
    
    services = {
        'Postgres (app)': ('localhost', 5432),
        'Postgres (Temporal)': ('localhost', 5433),
        'MinIO': ('localhost', 9000),
        'Temporal': ('localhost', 7233),
        'Temporal UI': ('localhost', 8080)
    }
    
    running_count = 0
    for service, (host, port) in services.items():
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                print(f"{GREEN}✓{RESET} {service} (port {port})")
                running_count += 1
            else:
                print(f"{RED}✗{RESET} {service} (port {port}) - not reachable")
        except Exception as e:
            print(f"{RED}✗{RESET} {service} (port {port}) - error: {e}")
    
    if running_count == 0:
        print(f"\n{YELLOW}⚠{RESET}  No infrastructure services running. Start with: make up")
    
    return running_count == len(services)

def what_can_run_without_docker():
    """List what can be tested without Docker."""
    print(f"\n{BOLD}What Can Run Without Docker:{RESET}")
    print(f"{GREEN}✓{RESET} Static code analysis (imports, syntax)")
    print(f"{GREEN}✓{RESET} Unit tests (mocked dependencies)")
    print(f"{GREEN}✓{RESET} Schema validation (model definitions)")
    print(f"{RED}✗{RESET} Integration tests (require Postgres)")
    print(f"{RED}✗{RESET} Workflow tests (require Temporal)")
    print(f"{RED}✗{RESET} Storage tests (require MinIO)")
    print(f"{RED}✗{RESET} End-to-end evaluation harness")
    print(f"{RED}✗{RESET} Core API server")
    print(f"{RED}✗{RESET} Temporal workers")

def main():
    print_header("AGORA System Diagnostic - End-to-End Testing Pre-Check")
    
    print(f"{BOLD}Checking system requirements for running AGORA end-to-end...{RESET}")
    
    # Run all checks
    docker_ok = check_docker()
    python_ok = check_python_env()
    structure_ok = check_project_structure()
    services_ok = check_infrastructure_services()
    
    # Summary
    print_header("Diagnostic Summary")
    
    if docker_ok and python_ok and structure_ok and services_ok:
        print(f"{GREEN}{BOLD}✓ System is ready for end-to-end testing!{RESET}\n")
        print(f"{BOLD}Next steps:{RESET}")
        print("1. Run evaluation harness: python scripts/run_evaluation.py --verbose")
        print("2. Start Core API: make dev-core-api")
        print("3. Start Workers: cd apps/worker && python -m temporalio.worker")
        print("4. Start Web UI: cd apps/web && npm install && npm run dev")
        return 0
    else:
        print(f"{YELLOW}{BOLD}⚠ System is not ready for end-to-end testing{RESET}\n")
        
        print(f"{BOLD}Required actions:{RESET}")
        
        if not docker_ok:
            print(f"{RED}1. Install and start Docker Desktop{RESET}")
            print("   → See Docs/getting_started/installation.md for instructions")
        
        if not services_ok and docker_ok:
            print(f"{YELLOW}2. Start infrastructure services{RESET}")
            print("   → Run: make up")
            print("   → Or: cd infra && docker compose up -d")
        
        if not python_ok:
            print(f"{YELLOW}3. Install Python dependencies{RESET}")
            print("   → Run: make install-db install-core-api")
        
        if not structure_ok:
            print(f"{RED}4. Fix project structure{RESET}")
            print("   → Ensure you're in the AGORA project root directory")
        
        print(f"\n{BOLD}Once Docker is installed and services are running:{RESET}")
        print("1. make up              # Start all infrastructure")
        print("2. make migrate-up      # Run database migrations")
        print("3. make test            # Run integration tests")
        print("4. make dev-core-api    # Start Core API")
        print("5. python scripts/run_evaluation.py --verbose  # Run evaluation harness")
        
        # Show what can be done now
        what_can_run_without_docker()
        
        return 1

if __name__ == "__main__":
    sys.exit(main())
