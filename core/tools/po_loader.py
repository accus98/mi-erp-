
import re
from core.db import Database

class POLoader:
    @staticmethod
    def load_po(env, file_path, lang, module_name='base'):
        """
        Parses a .po file and loads it into ir.translation.
        Simple parser for standard PO format:
        msgid "Source"
        msgstr "Target"
        """
        print(f"Loading translations for {lang} from {file_path}...")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Regex to find blocks
        # This is a basic parser. Professional ones use polib.
        # Handling multiline definitions is tricky with simple regex, 
        # but we assume standard 1 line per string for MVP or simplistic multiline.
        
        # Pattern: msgid "..." followed by msgstr "..."
        # We need to capture the content inside quotes.
        pattern = re.compile(r'msgid\s+"(.*?)"\s+msgstr\s+"(.*?)"', re.DOTALL)
        
        matches = pattern.findall(content)
        
        Translation = env['ir.translation']
        count = 0
        
        for source, target in matches:
            source = source.replace('\\"', '"').replace('\\n', '\n')
            target = target.replace('\\"', '"').replace('\\n', '\n')
            
            if not source or not target: continue
            
            # Auto-detect type?
            # Usually PO files correspond to Code or Views or Constraints.
            # Model data translations usually managed via XML or CSV.
            # We assume 'code' for generic PO loader unless mapped otherwise.
            
            # Check exist
            existing = Translation.search([
                ('type', '=', 'code'),
                ('src', '=', source),
                ('lang', '=', lang)
            ], limit=1)
            
            if existing:
                if existing[0].value != target:
                    existing[0].write({'value': target})
                    count += 1
            else:
                Translation.create({
                    'name': 'code', # Standard for code terms
                    'type': 'code',
                    'lang': lang,
                    'src': source,
                    'value': target,
                    'module': module_name, # Not in model yet, but useful future proofing
                    'state': 'translated'
                })
                count += 1
                
        print(f"Loaded {count} translations.")
