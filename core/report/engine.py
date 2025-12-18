import jinja2
from weasyprint import HTML, CSS
try:
    from core.registry import Registry
except ImportError:
    pass # Might be imported by registry

class ReportEngine:
    def __init__(self, env):
        self.env = env
        # Configurar Jinja2 Loader desde directorios de módulos
        # Assumes running from root
        self.loader = jinja2.FileSystemLoader(['addons/', 'core/reports/templates/'])
        self.env_jinja = jinja2.Environment(loader=self.loader)

    async def render_pdf(self, report_name, docids, data=None):
        """
        Renders a report to PDF bytes.
        :param report_name: Name of the report (e.g., 'sales.report_invoice')
        :param docids: List of IDs to render
        :param data: Optional extra data context
        """
        # 1. Obtener Datos
        # Assuming report_name maps to a model or we assume the caller knows the model
        # For a generic engine, we usually look up ir.actions.report to find the model.
        # For this prototype, we'll assume the caller passes the right context or we infer it.
        # Let's assume report_name is like 'module.template_name' and we need to know the model.
        # For simpliciy in prototype: The caller often passes the model docs directly or we browse them.
        
        # Real Odoo logic: look up ir.actions.report by name -> get model -> browse(docids)
        # Here we will assume docids are linked to a specific model provided in 'data' or inferred?
        # Let's assume the user of this engine invokes it with a known model context.
        
        # If we stick to the user's snippet:
        # docs = self.env[report_name].browse(docids) <-- This implies report_name IS the model name?
        # Usually report_name is 'sale.report_saleorder', model is 'sale.order'.
        
        # We will implement a generic basic version as requested.
        # User snippet: docs = self.env[report_name].browse(docids)
        # We will modify this to use data['model'] if available, or assume report_name is model.
        
        model_name = data.get('model') if data else report_name
        docs = await self.env[model_name].browse(docids).read() # Read data for template?
        # Browse implies objects. Logic:
        docs_objs = self.env[model_name].browse(docids)
        
        # 2. Renderizar HTML (Jinja2)
        # We need to find the template file. 
        # report_name 'sales.report_invoice' -> addons/sales/report_invoice.html?
        # Simple mapping for prototype:
        template_path = f"{report_name.replace('.', '/')}.html"
        
        try:
            template = self.env_jinja.get_template(template_path)
        except jinja2.TemplateNotFound:
             # Fallback or error
             print(f"Template not found: {template_path}")
             return None

        # Prepare context
        # We need to ensure 'docs' are accessible. 
        # In async ORM, accessing fields on 'docs' (browse records) triggers awaitable calls?
        # Jinja2 is synchronous. We must pre-fetch or use a sync-proxy wrapper.
        # FOR PROTOTYPE: We pre-read fields or pass raw read() dicts.
        # Better: Pass the browse objects but warn that lazy loading inside Jinja might fail in async.
        # FIX: We'll assume for now we pass a list of dicts (read result) as 'docs'.
        
        # Read all fields for now (expensive but safe for prototype)
        docs_data = await docs_objs.read() 
        
        html_string = template.render({
            'docs': docs_data,
            'user': self.env.user,
            'company': self.env.company,
            'data': data or {}
        })

        # 3. Convertir a PDF (WeasyPrint)
        base_css = CSS(string="""
            @page { size: A4; margin: 1cm; @bottom-center { content: counter(page); } }
            body { font-family: sans-serif; font-size: 12px; }
            table { width: 100%; border-collapse: collapse; }
            th { border-bottom: 1px solid black; }
            td { padding: 4px; }
        """)
        
        pdf_bin = HTML(string=html_string).write_pdf(stylesheets=[base_css])
        return pdf_bin
