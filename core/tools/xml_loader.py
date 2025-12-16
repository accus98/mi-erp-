import xml.etree.ElementTree as ET
from core.env import Environment

class XmlLoader:
    def __init__(self, env):
        self.env = env
    
    def load_file(self, file_path, module='base'):
        print(f"Loading XML file: {file_path}")
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        for record in root.findall('record'):
            self._process_record(record, module)
            
    def _process_record(self, record_node, module):
        xml_id = record_node.attrib.get('id')
        model_name = record_node.attrib.get('model')
        
        if not xml_id or not model_name:
            print("Skipping invalid record node (missing id or model)")
            return
            
        # 1. Check if exists (Update vs Create)
        # We need to construct domain manually because we might not have `get_object_reference` bound to env yet?
        # Actually Model is bound.
        
        IMD = self.env['ir.model.data']
        # Note: We rely on search with domain parser now?
        # search needs our new domain parser if we use complex domains. 
        # But here we can use simple chained search or assume AND if simpler parser.
        # Let's use simple list: [('module','=',module), ('name','=',xml_id)] implicit AND
        
        imd_recs = IMD.search([('module', '=', module), ('name', '=', xml_id)])
        
        current_res_id = None
        current_imd = None
        
        if imd_recs:
            current_imd = imd_recs[0]
            current_res_id = current_imd.res_id
        
        # 2. Parse Fields
        vals = {}
        for field in record_node.findall('field'):
            fname = field.attrib.get('name')
            fref = field.attrib.get('ref')
            ftype = field.attrib.get('type')
            feval = field.attrib.get('eval')
            
            fval = None
            
            if feval:
                try:
                    # Define context for eval
                    def ref(xml_id):
                        t_mod = module
                        t_name = xml_id
                        if '.' in xml_id:
                            t_mod, t_name = xml_id.split('.', 1)
                        res = IMD._xmlid_to_res_id(t_mod, t_name)
                        if not res:
                            raise ValueError(f"Reference not found: {xml_id}")
                        return res
                        
                    fval = eval(feval, {'ref': ref, 'True': True, 'False': False, 'None': None})
                    vals[fname] = fval
                except Exception as e:
                    print(f"Error evaluating {feval} in {xml_id}: {e}")
            elif ftype == 'xml' or (len(field) > 0 and not fref):
                # Serialize children to XML string
                # We want inner content, not the <field> tag itself.
                # ElementTree doesn't have "inner_xml".
                # Hack: serialize children and join.
                chunks = []
                if field.text: chunks.append(field.text)
                for child in field:
                    chunks.append(ET.tostring(child, encoding='unicode'))
                    if child.tail: chunks.append(child.tail)
                fval = "".join(chunks).strip()
                vals[fname] = fval
            elif fref:
                 # Reference handling
                target_mod = module
                target_name = fref
                if '.' in fref:
                    target_mod, target_name = fref.split('.', 1)
                
                # Resolve using helper
                ref_res_id = IMD._xmlid_to_res_id(target_mod, target_name)
                
                if ref_res_id:
                    vals[fname] = ref_res_id
                else:
                    print(f"Warning: Reference {fref} not found for field {fname}.")
            else:
                fval = field.text
                vals[fname] = fval
                
        # 3. Write/Create
        Model = self.env[model_name]
        
        if current_res_id:
            # Update
            rec = Model.browse([current_res_id])
            # Verify record actually exists (might be deleted from DB but IMD remains)
            # browse always returns object, check ids or via search?
            # Model.browse([id]) usually returns a recordset. 
            # We can check simple read.
            try:
                # Check if record still exists
                exists = Model.search([('id', '=', current_res_id)])
                if exists:
                    exists.write(vals)
                    print(f"Updated {model_name}: {xml_id}")
                    return
            except Exception:
                pass # Recreate if failed
                
            # If we are here, record was missing. Recreate logic falls through?
            # Or assume write worked.
            
        # Create
        rec = Model.create(vals)
        current_res_id = rec.id
        
        if current_imd:
             current_imd.write({'res_id': current_res_id})
        else:
             IMD.create({
                'name': xml_id,
                'module': module,
                'model': model_name,
                'res_id': current_res_id
            })
            
        print(f"Created {model_name}: {xml_id} -> ID {current_res_id}")
