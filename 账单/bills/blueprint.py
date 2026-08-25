"""账单：逻辑在本包；本 Blueprint 仅挂载本功能模板目录。"""

from flask import Blueprint

# 模板位于 modules/bills/templates/bills/*.html
bills_bp = Blueprint("bills", __name__, template_folder="templates")
