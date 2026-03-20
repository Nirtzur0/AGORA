export function asArray(value, key) {
  if (Array.isArray(value)) return value;
  if (key && Array.isArray(value?.[key])) return value[key];
  return [];
}

export function parseMaybeJson(value) {
  if (!value || typeof value !== 'string') return value;
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function normalizeJsonFields(record, fieldNames) {
  if (!record || typeof record !== 'object') return record;
  return fieldNames.reduce((result, fieldName) => {
    if (!(fieldName in result)) return result;
    return {
      ...result,
      [fieldName]: parseMaybeJson(result[fieldName]),
    };
  }, record);
}

export function normalizeArtifact(artifact) {
  return normalizeJsonFields(artifact, ['metadata']);
}

export function normalizeClaim(claim) {
  const normalized = normalizeJsonFields(claim, ['metadata']);
  return {
    ...normalized,
    evidence: asArray(normalized?.evidence),
  };
}

export function normalizeCritique(critique) {
  return normalizeJsonFields(critique, ['resolution']);
}

export function normalizeTask(task) {
  return normalizeJsonFields(task, ['payload']);
}

export function normalizeRuleCheck(ruleCheck) {
  return normalizeJsonFields(ruleCheck, ['details']);
}

export function normalizeSearchResponse(payload) {
  if (!payload || typeof payload !== 'object') return payload;
  return {
    ...payload,
    hits: asArray(payload.hits).map((hit) => normalizeJsonFields(hit, ['metadata'])),
  };
}
