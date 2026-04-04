import { readFile, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');
const checklistPath = path.join(projectRoot, 'docs', 'RESPONSIVE_SCREENSHOT_CHECKLIST.md');

const checkboxLinePattern = /^- \[([ x])\] `(docs\/screenshots\/responsive\/[^`]+\.png)`$/gm;

const originalContent = await readFile(checklistPath, 'utf8');
let matchedEntries = 0;
let existingEntries = 0;

const nextContent = originalContent.replace(checkboxLinePattern, (_match, _checked, relativePath) => {
  matchedEntries += 1;
  const absolutePath = path.join(projectRoot, relativePath.replace(/\//g, path.sep));
  const present = existsSync(absolutePath);
  if (present) {
    existingEntries += 1;
  }
  return `- [${present ? 'x' : ' '}] \`${relativePath}\``;
});

if (matchedEntries === 0) {
  throw new Error('No screenshot checklist entries were found to update.');
}

if (nextContent !== originalContent) {
  await writeFile(checklistPath, nextContent, 'utf8');
}

console.log(`Responsive screenshot checklist synced: ${existingEntries}/${matchedEntries} files present.`);

