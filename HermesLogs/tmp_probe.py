import os,sys,logging
sys.path.insert(0, r'C:\Users\user\Desktop\hermes_claude')
os.chdir(r'C:\Users\user\Desktop\hermes_claude')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [TEST] %(levelname)s %(message)s', handlers=[logging.StreamHandler(sys.stdout)])

# Check which process/module answers /chat
import importlib.util
spec = importlib.util.spec_from_file_location('server', r'C:\Users\user\Desktop\hermes_claude\hermes_rpc\server.py')
mod = importlib.util.module_from_spec(spec)
os.environ['NOUS_API_KEY'] = ''
os.environ['GEMINI_API_KEY'] = ''
# prevent uvicorn run
sys.stdout.write('\n=== LOADED_MODULE ===\n' + str(mod) + '\n=======\n')
spec.loader.exec_module(mod)
sys.stdout.write('MODULE_LOAD_OK\n')
