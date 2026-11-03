import {mountAdvisor} from '../../../../website/static/js/advisor-first-pass.js';
mountAdvisor(JSON.parse(document.getElementById('advisor-config').textContent));
