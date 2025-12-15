import re

def test_pattern():
    print("Testing Regex Logic")
    route_path = '/web/content/<string:model>/<int:id>/<string:field>'
    print(f"Original: {route_path}")
    
    pattern = route_path
    pattern = re.sub(r'<int:(\w+)>', r'(?P<\1>\\d+)', pattern)
    print(f"After Int: {pattern}")
    
    pattern = re.sub(r'<string:(\w+)>', r'(?P<\1>[^/]+)', pattern)
    print(f"After String: {pattern}")
    
    pattern = re.sub(r'<(\w+)>', r'(?P<\1>[^/]+)', pattern)
    print(f"After Default: {pattern}")
    
    try:
        regex = re.compile(f"^{pattern}$")
        print("Compile Success")
    except Exception as e:
        print(f"Compile Failed: {e}")

if __name__ == "__main__":
    test_pattern()
