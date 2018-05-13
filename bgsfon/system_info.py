from . import bgs
import json
import functools
from . import db

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)

bp = Blueprint('system_info', __name__, url_prefix='/system_info')

@bp.route('/', methods=('GET', 'POST'))
def get_system_info():
  return render_template('system_info/request_system.html')

@bp.route('/system_controller', methods=('GET', 'POST'))
def get_system_info3():
  if request.method == 'POST':
    error = None
    conn = db.get_db()
    s = bgs.System(conn,str(request.data))
    s = bgs.System(conn,"Naunin")
    print(s.get_controller_and_state(conn))
  return json.dumps([s.get_controller_and_state(conn)])