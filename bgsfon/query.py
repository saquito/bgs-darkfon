from . import bgs
import json
from . import db

# from flask import (
#     Blueprint, flash, g, redirect, render_template, request, session, url_for
# )

from flask import (
    Blueprint, render_template, request
)

bp = Blueprint('query', __name__, url_prefix='/query')

@bp.route('/', methods=('GET', 'POST'))
def get_system_info():
  return render_template('query/request_system.html')

@bp.route('/system_controller', methods=('GET', 'POST'))
def get_system_controller():
  if request.method == 'POST':
    conn = db.get_db()
    s = bgs.System(conn,request.data.decode('utf-8'))
  return json.dumps([s.get_controller_and_state(conn)])

@bp.route('/faction_state', methods=('GET', 'POST'))
def get_faction_state():
  if request.method == 'POST':
    conn = db.get_db()
    f = bgs.Faction(conn,request.data.decode('utf-8'))
    factions = [{"state":state} for state in f.get_current_factions(conn)]
  return json.dumps(factions)

@bp.route('/system_factions', methods=('GET', 'POST'))
def get_system_factions():
  result = []
  if request.method == 'POST':
    conn = db.get_db()
    star_system = bgs.System(conn,request.data.decode('utf-8'))
    if star_system:
      system_factions = star_system.get_current_factions(conn)
      for faction in system_factions:
        f = bgs.Faction(conn,faction)
        if f:
          state = f.get_state(conn)
          influence = f.get_current_influence_in_system(conn,star_system)
          if state and influence:
            faction_dict = {"name":faction,"state":state,"influence":"{0:.2f} %".format(influence*100.0)}
            result.append(faction_dict)
  return json.dumps(result)

