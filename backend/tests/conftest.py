import os
import sys
import tempfile

# Point the app at a throwaway database and upload folder before it is imported,
# so the tests never touch the real invoices.db
_tmp = tempfile.mkdtemp(prefix="invoice-tests-")
os.environ["INVOICE_DB_PATH"] = os.path.join(_tmp, "test.db")
os.environ["INVOICE_UPLOAD_DIR"] = os.path.join(_tmp, "uploads")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
