import { readFileSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const skillName = 'write-chinese-long-screenplay';
const skillPath = fileURLToPath(new URL('./SKILL.md', import.meta.url));
const resourceBase = fileURLToPath(new URL('./', import.meta.url));
const rank = 600;

export const name = skillName;
export const inject = ['skills'];

export function apply(ctx) {
  const initial = parseSkill(readFileSync(skillPath, 'utf8'));
  if (initial === undefined) {
    throw new Error(`${skillName}: root SKILL.md has invalid frontmatter`);
  }

  ctx.skills.registerProvider(() => ({
    name: skillName,
    async list(options) {
      options?.signal?.throwIfAborted();
      return [toCandidate(await loadSkill())];
    },
    async get(candidate, options) {
      options?.signal?.throwIfAborted();
      if (candidate.name !== skillName) return undefined;
      return toDefinition(await loadSkill());
    },
  }));
}

async function loadSkill() {
  const raw = await readFile(skillPath, 'utf8');
  const skill = parseSkill(raw);
  if (skill === undefined) {
    throw new Error(`${skillName}: root SKILL.md has invalid frontmatter`);
  }
  return skill;
}

function parseSkill(raw) {
  const match = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/);
  if (!match) return undefined;
  const fields = {};
  for (const line of match[1].split(/\r?\n/)) {
    const separator = line.indexOf(':');
    if (separator < 0) continue;
    fields[line.slice(0, separator).trim()] = line.slice(separator + 1).trim();
  }
  const nameValue = fields.name;
  const description = fields.description;
  if (nameValue !== skillName || !description) return undefined;
  return { name: nameValue, description, content: match[2].trim() };
}

function toCandidate(skill) {
  return {
    name: skill.name,
    description: skill.description,
    invocation: { modelInvocable: true, userInvocable: true },
    provider: skillName,
    source: 'bundled',
    resourceBase: { kind: 'directory', path: resourceBase },
    rank,
    locator: skillPath,
    path: skillPath,
  };
}

function toDefinition(skill) {
  return {
    ...toCandidate(skill),
    content: skill.content,
  };
}
