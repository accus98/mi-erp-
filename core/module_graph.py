
import os
import ast

class ModuleGraph:
    def __init__(self, addons_path):
        self.addons_path = addons_path
        self.modules = {} # name -> {depends: [], path: ...}
        self.graph = {}   # name -> set(deps)

    def scan(self):
        """
        Scan addons directory for modules and manifests.
        """
        if not os.path.exists(self.addons_path):
            return

        for item in os.listdir(self.addons_path):
            if item.startswith('.'): continue
            mod_path = os.path.join(self.addons_path, item)
            manifest_path = os.path.join(mod_path, '__manifest__.py')
            
            if os.path.isdir(mod_path) and os.path.exists(manifest_path):
                try:
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        data = ast.literal_eval(f.read())
                        depends = data.get('depends', [])
                        self.modules[item] = {
                            'depends': depends,
                            'path': mod_path
                        }
                        self.graph[item] = set(depends)
                except Exception as e:
                    print(f"Error reading manifest for {item}: {e}")

    def topological_sort(self):
        """
        Returns list of module names in load order.
        """
        # Kahn's Algorithm
        # 1. Calculate in-degree (number of Dependencies preventing load)
        # Wait, if A depends on B. B must load first.
        # Graph: A -> B (A depends on B). A has outgoing edge to B.
        # Load order should be reverse topological?
        # Or standard topologial if verify A -> B means B comes after A?
        # NO.
        # Dependency Graph: Node is module. Edge A -> B means "A depends on B".
        # Loading: B must be loaded, then A.
        # So we need "B, A".
        # Standard Topological Sort on (Depends On) graph gives:
        # source nodes first? No.
        # Topological Sort gives: for every edge u -> v, u comes before v.
        # If A -> B (A depends on B). Topo sort: A, B.
        # BUT we need B to load BEFORE A.
        # So we want the REVERSE of Topological Sort of Dependency Graph.
        # OR we perform Topological Sort on the "Enables" graph (B -> A).
        
        # Let's use the Dependency Graph: A -> B (A depends on B).
        # We want B first.
        # So essentially we want to pick nodes with 0 dependencies first.
        # Then remove them from the graph.
        
        result = []
        
        # Working Copy
        deps = {k: set(v) for k,v in self.graph.items()}
        
        # Filter dependencies that are NOT in the addons list (e.g. 'base', 'web' if they are core or not scanned?)
        # Ensure all deps exist in 'deps' keys. If not, assume they are core/already loaded and remove them.
        all_modules = set(deps.keys())
        for m in all_modules:
            # Intersection: Only wait for modules that are in our list.
            # External/Core dependencies are assumed satisfied.
            deps[m] = deps[m].intersection(all_modules)
            
        while True:
            # Find nodes with 0 dependencies
            ready = [node for node, d in deps.items() if not d]
            
            if not ready:
                if not deps:
                    break # Done
                else:
                    # Cycle detected!
                    print(f"CRITICAL: Circular Dependency detected in modules: {deps.keys()}")
                    # Fallback: Load remaining arbitrarily to allow partial boot debug
                    result.extend(deps.keys())
                    break
            
            # Sort alphabetically for deterministic behavior among siblings
            ready.sort()
            
            for node in ready:
                result.append(node)
                del deps[node]
                
            # Remove satisfied dependencies
            for node, d in deps.items():
                d.difference_update(ready)
                
        return result

def load_modules_topological(addons_path):
    graph = ModuleGraph(addons_path)
    graph.scan()
    return graph.topological_sort()
