import jinja2
from weasyprint import HTML, CSS
try:
    from core.registry import Registry
except ImportError:
    pass # Might be imported by registry

class ReportRecordProxy:
    """
    Wrapper síncrono para objetos Async. 
    Se usa SOLO dentro de Jinja2.
    Requiere que los datos hayan sido precargados en caché o leídos previamente.
    """
    def __init__(self, record, extra_context=None):
        self._record = record
        self._context = extra_context or {}

    def __getattr__(self, name):
        # Intentamos obtener del caché síncrono del Environment
        # 1. Si es un campo del modelo
        if name in self._record._fields:
            field = self._record._fields[name]
            
            # Hack: Acceso directo al caché síncrono (self.env.cache es un dict)
            # Clave de cache: (model_name, id, field_name)
            val = self._record.env.cache.get((self._record._name, self._record.id, name))
            
            if val is None:
                return None # O string vacío
            
            # Si es relacional, devolvemos otro Proxy o lista de Proxies
            if field._type == 'many2one':
                if not val: return None
                # val es ID
                comodel = self._record.env[field.comodel_name].browse(val)
                return ReportRecordProxy(comodel)
                
            elif field._type in ('one2many', 'many2many'):
                # val es lista de IDs
                comodel = self._record.env[field.comodel_name].browse(val)
                return [ReportRecordProxy(r) for r in comodel]
                
            return val
            
        return getattr(self._record, name)

class ReportEngine:
    def __init__(self, env):
        self.env = env
        # Configurar Jinja2 Loader desde directorios de módulos
        self.loader = jinja2.FileSystemLoader(['addons/', 'core/reports/templates/'])
        self.env_jinja = jinja2.Environment(loader=self.loader)

    async def render_pdf(self, report_name, docids, data=None):
        """
        Renders a report to PDF bytes using Async->Sync Proxy pattern.
        """
        model_name = data.get('model') if data else report_name
        docs = self.env[model_name].browse(docids)
        
        # --- LA MAGIA: PRE-FETCHING MASIVO ---
        # Antes de llamar a Jinja (Síncrono), debemos cargar TODO lo que el reporte necesite
        # en el caché del Environment asíncronamente.
        
        # 1. Identificar campos a leer (Optimización futura: leer del template HTML)
        # Por ahora, leemos TODOS los campos almacenados del modelo principal
        await docs.read() 
        
        # 2. TRUCO: Pre-cargar relaciones comunes (Nivel 1 de profundidad)
        # Iteramos los campos relaciones y hacemos prefetch
        fields_to_fetch = [f for f, field in docs._fields.items() if field._type in ('one2many', 'many2many', 'many2one')]
        
        # Hacemos un "ensure" de estos campos para disparar la carga en caché
        if fields_to_fetch:
             await docs.read(fields_to_fetch)
             
             # Nivel 2: Pre-cargar las líneas (ej. invoice_lines)
             # Esto es un poco "fuerza bruta" pero asegura que Jinja no falle.
             for fname in fields_to_fetch:
                 field = docs._fields[fname]
                 if field._type in ('one2many', 'many2many'):
                     # Obtener todos los IDs de las lineas
                     lines = await docs.mapped(fname)
                     if lines:
                         await lines.read() # Carga las líneas en caché

        # 3. Envolver en Proxies
        docs_proxies = [ReportRecordProxy(d) for d in docs]
        
        # 4. Renderizar HTML (Jinja2)
        template_path = f"{report_name.replace('.', '/')}.html"
        try:
            template = self.env_jinja.get_template(template_path)
        except jinja2.TemplateNotFound:
             print(f"Template not found: {template_path}")
             return None

        html_string = template.render({
            'docs': docs_proxies, # Pasamos los proxies, no los dicts
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
