import Ajv from 'ajv/dist/2020.js';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../../',import.meta.url));
const folder=process.argv[2];
const schema=JSON.parse(readFileSync(new URL('./schemas/projections.json',import.meta.url)));
const ajv=new Ajv({allErrors:true});ajv.addSchema(schema);
const manifest=JSON.parse(readFileSync(resolve(folder,'data-manifest.json')));
let count=0;
for(const [feature,component] of Object.entries(manifest.components)){
  if(!component.files)continue;
  if(!/^[a-f0-9]{64}$/.test(component.version))throw new Error('Invalid component version');
  if(new Set(component.civilizations).size!==component.civilizations.length)throw new Error('Duplicate eligibility');
  const validate=ajv.compile({$ref:`${schema.$id}#/$defs/${feature}`});
  for(const [name,file] of Object.entries(component.files)){
    const bytes=readFileSync(resolve(folder,file.url.slice(1)));
    if(createHash('sha256').update(bytes).digest('hex')!==file.sha256)throw new Error('Export hash mismatch');
    if(['overview','search','calculation-roster'].includes(name))continue;
    if(!validate(JSON.parse(bytes)))throw new Error(`Schema mismatch: ${feature}/${name}: ${ajv.errorsText(validate.errors)}`);
    count++;
  }
}
console.log(`Validated ${count} public feature projections against v1 schemas`);
