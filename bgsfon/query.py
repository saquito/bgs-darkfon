from . import bgs
import json
from . import db

# from flask import (
#     Blueprint, flash, g, redirect, render_template, request, session, url_for
# )

from flask import (
    Blueprint, render_template, request,send_from_directory
)

bp = Blueprint('query', __name__, url_prefix='/query')
bp_media = Blueprint('media', __name__, url_prefix='/media')

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
            faction_dict = {"name":faction,"state":state,"influence":"{0:.2f}".format(influence*100.0)}
            result.append(faction_dict)
  if result:
    print(result)
    result = sorted(result,key=lambda x: float(x["influence"]),reverse=True)
  return json.dumps(result)

@bp.route('/near_systems', methods=('GET', 'POST'))
def get_near_systems():
  result = []
  if request.method == 'POST':
    conn = db.get_db()
    star_system = bgs.System(conn,request.data.decode('utf-8'))
    if star_system:
      near_systems = star_system.get_closest_systems(conn, 10)
      for near_sys in near_systems:
        num_factions = len(bgs.System(conn,near_sys["system"]).get_factions(conn))
        result.append({"name":near_sys["system"],"distance":near_sys["distance"],"num_factions":num_factions})
  if result:
    result = sorted(result,key=lambda x: float(x["distance"]))
  return json.dumps(result)

@bp.route('/next_expansion', methods=('GET', 'POST'))
def get_next_expansion():
  result = []
  if request.method == 'POST':
    conn = db.get_db()
    star_system = bgs.System(conn,request.data.decode('utf-8'))
    if star_system:
        next_expansion = star_system.get_next_expansion_system(conn)["system"]
        print(next_expansion)
        result = next_expansion
  return next_expansion

@bp.route('/near_systems_list', methods=('GET', 'POST'))
def get_near_systems_list():
  return render_template('query/near_systems_list.html')


@bp.route('/faction_system_list', methods=('GET', 'POST'))
def get_faction_system_list():
  return render_template('query/faction_system_list.html')

@bp.route('/system_info', methods=('GET', 'POST'))
def get_system_info_pane():
  return render_template('query/system_info.html')

@bp.route('/system_info_test', methods=('GET', 'POST'))
def get_system_info_test_pane():
  return render_template('query/system_info_test.html')

@bp_media.route('/media/<path:filename>')
def download_file(filename):
  return send_from_directory("media", filename, as_attachment=True)
