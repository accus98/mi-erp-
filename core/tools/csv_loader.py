import csv
from core.env import Environment

class CsvLoader:
    def __init__(self, env):
        self.env = env
    
    def load_file(self, file_path, model_name='ir.model.access'):
        print(f"Loading CSV file: {file_path}")
        try:
            with open(file_path, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    self._process_row(row, model_name)
                    count += 1
                print(f"Loaded {count} rows into {model_name}")
        except Exception as e:
            print(f"Error loading CSV {file_path}: {e}")

    def _process_row(self, row, model_name):
        # Specific logic for ir.model.access
        if model_name == 'ir.model.access':
            # Row mapping: id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
            # We need to resolve model_id:id which is an XML ID in ir.model to a DB ID of ir.model
            
            # 1. Resolve Model
            xml_model_id = row.get('model_id:id')
            if xml_model_id:
                # Expect 'model_res_partner' or similar representing the record in ir.model
                # But currently we don't have XML IDs for ir.model records created by Registry sync.
                # Registry sync creates ir.model records but doesn't create ir.model.data entries for them!
                # IMPORTANT: Automation gap.
                # Workaround: map model name directly if passed? Or lookup ir.model by 'model' field?
                # Standard Odoo CSV uses External ID.
                # Let's assume for this MVP we pass model NAME in a custom column 'model_name' 
                # or we try to be smart.
                pass
            
            # Simple hack for MVP: Use 'model_name' column if present
            target_model_name = row.get('model_name') # e.g. res.partner
            if target_model_name:
                m = self.env['ir.model'].search([('model', '=', target_model_name)])
                if m:
                    row['model_id'] = m[0].id
                else:
                    print(f"Warning: Model {target_model_name} not found.")
                    return
            
            # Clean up keys
            vals = {
                'name': row.get('name'),
                'model_id': row.get('model_id'),
                'group_id': row.get('group_id:id') or 'everyone', # Dummy
                'perm_read': int(row.get('perm_read')),
                'perm_write': int(row.get('perm_write')),
                'perm_create': int(row.get('perm_create')),
                'perm_unlink': int(row.get('perm_unlink')),
            }
            
            self.env[model_name].create(vals)

