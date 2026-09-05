"""Versioned published explanations travel with the scores they describe."""
import json
from pathlib import Path

def load_methodology():
    return json.loads(Path(__file__).with_name('ranking_methods.json').read_text(encoding='utf-8'))

def load_published_methods(golden_dir):
    path = Path(golden_dir) / 'derived_data_v3.metadata.json'
    if not path.exists(): return {'schema_version':1, 'methods':{}}
    return json.loads(path.read_text(encoding='utf-8')).get('methodology', {'schema_version':1, 'methods':{}})
