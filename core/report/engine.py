
import asyncio
from jinja2 import Environment as JinjaEnv, DebugUndefined
import xml.etree.ElementTree as ET
import re

class ReportEngine:
    def __init__(self, env):
        self.env = env
        self.jinja_env = JinjaEnv(undefined=DebugUndefined)

    async def render(self, report_name, docids, data=None):
        """
        Render a report to HTML.
        :param report_name: ID/Name of the view (e.g. 'account.report_invoice')
        :param docids: List of IDs to render
        :param data: Optional context data
        :return: Rendered HTML string.
        """
        # 1. Fetch Report Action/View
        # Assuming report_name is a View Name/ID (QWeb View) rather than Action for MVP
        view = await self._get_view(report_name)
        if not view:
            raise ValueError(f"Report View '{report_name}' not found.")
            
        # 2. Resolve Inheritance (Validation)
        # Assuming View Manager provides 'arch_combined'
        # Current ir.ui.view model handles basic inheritance. 
        # But we need to walk the tree.
        # Let's implement full 'get_combined_arch' logic here or in Model.
        # For MVP, assume view.arch is valid or handle single level?
        # Actually Model.apply_inheritance exists.
        
        # We need to trace upstream (Base) -> Downstream (Extensions)
        # If 'report_name' is the Base, we search for extensions.
        # If 'report_name' is an Extension, we find base.
        # Typically we render the Base View (report_name refers to base).
        
        arch = await self._get_combined_arch(view)
        
        # 3. Transpile QWeb -> Jinja2
        template_str = self._transpile_qweb(arch)
        
        # 4. Fetch Data
        # docs = Browse Records
        model_name = view.model
        if not model_name:
             # Generic
             model_name = 'base' # Dummy?
             docs = []
        else:
             docs = self.env[model_name].browse(docids)
             # Prefetch? await docs.read()?
             # QWeb access usually triggers lazy loading (FieldFuture).
             # So we pass docs directly.
             
        # 5. Render
        template = self.jinja_env.from_string(template_str)
        
        render_vals = {
            'docs': docs,
            'user': self.env.user,
            'data': data or {}
        }
        
        return template.render(render_vals)

    async def render_pdf(self, report_name, docids, data=None):
        """
        Render report to PDF bytes.
        """
        html = await self.render(report_name, docids, data)
        
        # Try WeasyPrint
        try:
            from weasyprint import HTML
            import io
            buffer = io.BytesIO()
            HTML(string=html).write_pdf(buffer)
            return buffer.getvalue()
        except ImportError:
            print("Report Warning: WeasyPrint not installed. Returning HTML bytes.")
            return html.encode('utf-8')
        except Exception as e:
            print(f"Report Error (PDF): {e}")
            raise e

    async def _get_view(self, name):
        # Allow ID or XMLID (String)
        # For MVP: 'module.name' string or pure name.
        # Use Search.
        views = await self.env['ir.ui.view'].search([('name', '=', name)])
        if not views:
             # Try assuming it's the model? No.
             return None
        return views[0]

    async def _get_combined_arch(self, view):
        # 1. Get Base Arch
        arch = view.arch
        
        # 2. Search for inheriting views (mode='extension') associated with this view
        # inherit_id = view.id
        extensions = await self.env['ir.ui.view'].search([
            ('inherit_id', '=', view.id),
            ('mode', '=', 'extension')
        ], order='priority asc') # Apply by priority
        
        # 3. Apply extensions in order
        for ext in extensions:
            # We need to read arch of ext
            # Model.apply_inheritance(base, extension)
            arch = self.env['ir.ui.view'].apply_inheritance(arch, ext.arch)
            
        return arch

    def _transpile_qweb(self, xml_str):
        """
        Convert QWeb XML (t-foreach, t-field) to Jinja2.
        """
        root = ET.fromstring(xml_str)
        
        def process_node(node):
            # Start Tag
            tag = node.tag
            attribs = node.attrib
            
            # Logic Directives
            # 1. t-foreach
            prefix = ""
            suffix = ""
            
            if 't-foreach' in attribs:
                var = attribs.pop('t-foreach')
                as_var = attribs.pop('t-as', 'item')
                prefix += f"{{% for {as_var} in {var} %}}"
                suffix = f"{{% endfor %}}{suffix}"
            
            if 't-if' in attribs:
                condition = attribs.pop('t-if')
                prefix += f"{{% if {condition} %}}"
                suffix = f"{{% endif %}}{suffix}"
                
            # Content Directives
            text_content = node.text or ""
            
            if 't-field' in attribs:
                field = attribs.pop('t-field')
                # Replace content with {{ field }}
                # Also handle widget logic here? For MVP: format(field)
                text_content = f"{{{{ {field} }}}}"
                node.text = text_content
                
            if 't-esc' in attribs: # Escape HTML
                expr = attribs.pop('t-esc')
                text_content = f"{{{{ {expr} }}}}"
                node.text = text_content

            if 't-raw' in attribs: # No Escape
                expr = attribs.pop('t-raw')
                text_content = f"{{{{ {expr} | safe }}}}"
                node.text = text_content
                
            # Recursion
            inner_html = ""
            if node.text: inner_html += node.text
            for child in node:
                inner_html += process_node(child)
                if child.tail: inner_html += child.tail
            
            # Reconstruct Tag (Approximation)
            # Jinja blocks usually wrap the tag.
            # <div t-if="cond">...</div> -> {% if cond %}<div>...</div>{% endif %}
            
            # Attribs to string
            attrs_str = " ".join([f'{k}="{v}"' for k, v in attribs.items()])
            if attrs_str: attrs_str = " " + attrs_str
            
            tag_open = f"<{tag}{attrs_str}>"
            tag_close = f"</{tag}>"
            
            return f"{prefix}{tag_open}{inner_html}{tag_close}{suffix}"

        # Root might be <data> or <template>. 
        # If data, process children.
        # But simple views usually are <div>...</div>
        
        # ET.tostring helper won't work well with our custom wrapping.
        # We manually process.
        
        result = process_node(root)
        
        # Remove Root Tag wrapper if it was artificial? 
        # Usually view arch has a root.
        
        return result
