#! /usr/bin/env python
#-*- coding: utf-8 -*-

###########################################################################
##                                                                       ##
## Copyrights Etienne Chové <chove@crans.org> 2009                       ##
##                                                                       ##
## This program is free software: you can redistribute it and/or modify  ##
## it under the terms of the GNU General Public License as published by  ##
## the Free Software Foundation, either version 3 of the License, or     ##
## (at your option) any later version.                                   ##
##                                                                       ##
## This program is distributed in the hope that it will be useful,       ##
## but WITHOUT ANY WARRANTY; without even the implied warranty of        ##
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         ##
## GNU General Public License for more details.                          ##
##                                                                       ##
## You should have received a copy of the GNU General Public License     ##
## along with this program.  If not, see <http://www.gnu.org/licenses/>. ##
##                                                                       ##
###########################################################################

###########################################################################
## database connection

import sys, os, cgi, Cookie, datetime
root_folder = os.environ["OSMOSE_ROOT"]
sys.path.append(root_folder)
from tools import utils

translate = utils.translator()
PgConn    = utils.get_dbconn()
PgCursor  = PgConn.cursor()
website = "osmose.openstreetmap.fr"

###########################################################################
## form fields

form = cgi.FieldStorage()

lat    = int(float(form.getvalue("lat", "0"))*1000000)
lon    = int(float(form.getvalue("lon", "0"))*1000000)
err_id = form.getvalue("item", "").split(",")
err_id = ",".join([str(int(x)) for x in err_id if x])
source = form.getvalue("source", "")
user   = utils.pg_escape(unicode(form.getvalue("user", "")))
level  = form.getvalue("level", None)
zoom   = int(form.getvalue("zoom", "10"))
bbox   = form.getvalue("bbox", None)
if level:
  level = level.split(",")
  level = ",".join([str(int(x)) for x in level if x])

if bbox:
  bbox = bbox.split(",")
  try:
    minlon = int(1000000*float(bbox[0]))
    minlat = int(1000000*float(bbox[1]))
    maxlon = int(1000000*float(bbox[2]))
    maxlat = int(1000000*float(bbox[3]))
  except ValueError:
    minlon = lon - 100000
    minlat = lat - 100000
    maxlon = lon + 100000
    maxlat = lat + 100000


###########################################################################
## page headers

print "Content-Type: text/plain; charset=utf-8"

cki = Cookie.SimpleCookie()
if os.environ.has_key('HTTP_COOKIE'):
    cki.load(os.environ['HTTP_COOKIE'])
cki["lastLat"] = form.getvalue("lat", "0")
cki["lastLat"]['expires'] = (datetime.datetime.now() + datetime.timedelta(days=365)).strftime("%a, %d %b %Y %H:00:00 GMT")
cki["lastLat"]['path']    = '/'
cki["lastLon"] = form.getvalue("lon", "0")
cki["lastLon"]['expires'] = (datetime.datetime.now() + datetime.timedelta(days=365)).strftime("%a, %d %b %Y %H:00:00 GMT")
cki["lastLon"]['path']    = '/'
cki["lastZoom"] = form.getvalue("zoom", "0")
cki["lastZoom"]['expires'] = (datetime.datetime.now() + datetime.timedelta(days=365)).strftime("%a, %d %b %Y %H:00:00 GMT")
cki["lastZoom"]['path']    = '/'
cki["lastLevel"] = form.getvalue("level", "1")
cki["lastLevel"]['expires'] = (datetime.datetime.now() + datetime.timedelta(days=365)).strftime("%a, %d %b %Y %H:00:00 GMT")
cki["lastLevel"]['path']    = '/'
cki["lastItem"] = form.getvalue("item", "")
cki["lastItem"]['expires'] = (datetime.datetime.now() + datetime.timedelta(days=365)).strftime("%a, %d %b %Y %H:00:00 GMT")
cki["lastItem"]['path']    = '/'
if cki:
    print cki
            
###########################################################################
## data

data_type = { "N": "node",
              "W": "way",
              "R": "relation",
              "I": "infos",
            }

print
print "\t".join(["lat", "lon", "marker_id", "icon", "iconSize", "iconOffset", "html"])

if (not user) and (not source) and (zoom < 6):
    sys.exit(0)

# TRANSLATORS: link to tooltip help
url_help = _("http://wiki.openstreetmap.org/wiki/Osmose/errors")
sqlbase  = """
SELECT marker.id,
       marker.item,
       marker.source,
       marker.class,
       marker.elems,
       marker.subclass,
       marker.lat,
       marker.lon,
       dynpoi_class.title,
       marker.subtitle,
       dynpoi_update_last.timestamp,
       elem0.data_type AS elem0_data_type,
       elem0.id AS elem0_id,
       elem0.tags AS elem0_tags,
       elem1.data_type AS elem1_data_type,
       elem1.id AS elem1_id,
       elem1.tags AS elem1_tags,
       elem2.data_type AS elem2_data_type,
       elem2.id AS elem2_id,
       elem2.tags AS elem2_tags,"""

for f in xrange(5):
    sqlbase += """fix%d.elem_data_type AS fix%d_elem_data_type,
       fix%d.elem_id AS fix%d_elem_id,
       fix%d.tags_create AS fix%d_tags_create,
       fix%d.tags_modify AS fix%d_tags_modify,
       fix%d.tags_delete AS fix%d_tags_delete,""" % (10 * (f, ))

sqlbase += """0
FROM marker
INNER JOIN dynpoi_class
  ON marker.source=dynpoi_class.source AND marker.class=dynpoi_class.class
INNER JOIN dynpoi_update_last
  ON marker.source = dynpoi_update_last.source
JOIN dynpoi_item
  ON marker.item = dynpoi_item.item
LEFT JOIN marker_elem elem0
  ON elem0.marker_id = marker.id AND elem0.elem_index = 0
LEFT JOIN marker_elem elem1
  ON elem1.marker_id = marker.id AND elem1.elem_index = 1
LEFT JOIN marker_elem elem2
  ON elem2.marker_id = marker.id AND elem2.elem_index = 2"""
for f in xrange(5):
    sqlbase += """LEFT JOIN marker_fix fix%d
  ON fix%d.marker_id = marker.id AND fix%d.diff_index = %d """ % (4 * (f, ))

if user:
    sqlbase += """INNER JOIN marker_elem
  ON marker.id = marker_elem.marker_id AND marker_elem.username = '%s' """ % user

sqlbase += """WHERE %s AND
  %s AND
  dynpoi_update_last.timestamp > (now() - interval '3 months')
ORDER BY ABS(lat-%d)+ABS(lon-%d) ASC
LIMIT 200;"""

sqlbase_count  = """
SELECT count(*)
FROM marker
INNER JOIN dynpoi_update_last
  ON marker.source = dynpoi_update_last.source """

if user:
    sqlbase_count += """INNER JOIN marker_elem
  ON marker.id = marker_elem.marker_id AND marker_elem.username = '%s' """ % user

if level:
    sqlbase_count += """INNER JOIN dynpoi_class
  ON marker.source = dynpoi_class.source AND marker.class = dynpoi_class.class """

sqlbase_count += """WHERE %s AND
  %s AND
  dynpoi_update_last.timestamp > (now() - interval '3 months')
LIMIT 310;"""

if source:
    sources = source.split(",")
    source2 = []
    for source in sources:
        source = source.split("-")
        if len(source)==1:
            source2.append("(marker.source=%d)"%int(source[0]))
        else:
            source2.append("(marker.source=%d AND marker.class=%d)"%(int(source[0]), int(source[1])))
    sources2 = " OR ".join(source2)
    where = "(%s)" % sources2
elif err_id:
    where = "(marker.item IN (%s))" % err_id
else:
    where = "1=1"

if level:
    where += " AND dynpoi_class.level IN (%s)" % level

###########################################################################
## sql querry

if bbox:
    lat = (minlat+maxlat) / 2
    lon = (minlon+maxlon) / 2

    step = 0.001 * 1000000

    num_steps = 0
    done = False

    while not done and num_steps < 10:

        num_steps += 1
        tmp_minlat = lat - step
        tmp_maxlat = lat + step
        tmp_minlon = lon - step
        tmp_maxlon = lon + step

        if (tmp_minlat < minlat and tmp_maxlat > maxlat and
            tmp_minlon < minlon and tmp_maxlon > maxlon):
            done = True
            bboxsql = ("(marker.lat BETWEEN %d AND %d) AND (marker.lon BETWEEN %d and %d)" %
                   (minlat, maxlat, minlon, maxlon))
            break

        bboxsql = ("(marker.lat BETWEEN %d AND %d) AND (marker.lon BETWEEN %d and %d)" %
                   (tmp_minlat, tmp_maxlat, tmp_minlon, tmp_maxlon))

        sql = sqlbase_count % (where, bboxsql)
        sql = sql.replace("--","+")
        PgCursor.execute(sql)
        num_results = PgCursor.fetchone()[0]

        if num_results > 300:
            step = step * 0.75
        elif num_results >= 100:
            done = True
        elif num_results > 0:
            step *= 2
        else:
            step *= 4

else:
    bboxsql = "1=1"

sql = sqlbase % (where, bboxsql, lat, lon)
sql = sql.replace("--","+")

#try:
#    open("/tmp/osmose-last.sql","a").write(sql+"\n")
#except:
#    pass

PgCursor.execute(sql)
results = PgCursor.fetchall()

###########################################################################
## print results

for res in results:
    lat       = str(float(res["lat"])/1000000)
    lon       = str(float(res["lon"])/1000000)
    error_id  = res["id"]
    title     = translate.select(res["title"])
    subtitle  = translate.select(res["subtitle"])
    b_date    = res["timestamp"] or ""
    item      = res["item"] or 0
    
    ############################################################
    ## build html

    html  = "<div class=\"bulle_msg\">"
    html += "<div class='closebubble'>"
    html += "<div><a href='#' onclick=\"closeBubble('%s');return false;\"><b>&nbsp;X&nbsp;</b></a></div>" % error_id
    html += "<div class=\"help\"><a target=\"_blank\" href='%s#%d'>&nbsp;?&nbsp;</a></div>" % (url_help, item)
    html += "</div>"
    html += "<div class=\"bulle_err\">"
    html += "<b>%s</b><br>%s<br>"%(title, subtitle)
    html += "</div>"

    elems = []
    if res["elem0_data_type"]:
        elems.append([data_type[res["elem0_data_type"]], res["elem0_id"], res["elem0_tags"]])
    if res["elem1_data_type"]:
        elems.append([data_type[res["elem1_data_type"]], res["elem1_id"], res["elem1_tags"]])
    if res["elem2_data_type"]:
        elems.append([data_type[res["elem2_data_type"]], res["elem2_id"], res["elem2_tags"]])

    new_elems = []
    for f in xrange(5):
        if res["fix%d_elem_data_type" % f]:
            found = False
            for e in elems:
                if e[0] == data_type[res["fix%d_elem_data_type" % f]] and e[1] == res["fix%d_elem_id" % f]:
                    e.append((res["fix%d_tags_create" % f],
                              res["fix%d_tags_modify" % f],
                              res["fix%d_tags_delete" % f],
                              f))
                    found = True
                    break
            if not found:
                new_elems.append((res["fix%d_tags_create" % f],
                                  res["fix%d_tags_modify" % f],
                                  res["fix%d_tags_delete" % f],
                                  f))

    for e in elems:
        html += "<div class=\"bulle_elem\">"
        if e[0] != "infos":
            html += "<b><a target=\"_blank\" href=\"http://www.openstreetmap.org/browse/%s/%s\">%s %s</a></b>"%(e[0], e[1], e[0], e[1])
            html += " <a href=\"javascript:iFrameLoad('http://rawedit.openstreetmap.fr/edit/%s/%s');\">rawedit</a>"%(e[0], e[1])
        if e[0] == "relation" and "boundary" in e[2]:
            html += " <a target=\"_blank\" href=\"http://analyser.openstreetmap.fr/cgi-bin/index.py?relation=%s\">analyse1</a>"%e[1]
            html += " <a target=\"_blank\" href=\"http://osm3.crans.org/osmbin/analyse-relation?%s\">analyse2</a>"%e[1]
        if e[0] == "node":
            html += " <a href=\"http://localhost:8111/import?url=http://www.openstreetmap.org/api/0.6/node/%d\" target=\"hiddenIframe\">josm</a>" % e[1]
        if e[0] == "way" or e[0] == "relation":
            html += " <a href=\"http://localhost:8111/import?url=http://www.openstreetmap.org/api/0.6/%s/%d/full\" target=\"hiddenIframe\">josm</a>" % (e[0], e[1])
        html += "<br>"

        for i in xrange(3, len(e)):
            html += "<div class='fix'>"
            html += "<a class='link' href='http://localhost:8111/import?url=http://%s/utils/fix-error.py?id=%s&fix=%s' target='hiddenIframe'>josm fix</a>"%(website, error_id, e[i][3])

            for (k, v) in e[i][0].items():
                html += "<div class='add'> + <b>" + k + "</b> = " + v + "<br></div>"
            for (k, v) in e[i][1].items():
                html += "<div class='mod'> ~ <b>" + k + "</b> = " + v + "<br></div>"
            for k in e[i][2]:
                html += "<div class='del'> - <b>" + k + "</b></div>"
            html += "</div>"

        for t in e[2].items():
            html += "<b>%s</b> = %s<br>"%(t[0], t[1])
        html += "</div>"

    for e in new_elems:
        html += "<div class=\"bulle_elem\">"
        html += "<div class='fix'>"
        html += "<a class='link' href='http://localhost:8111/import?url=http://%s/utils/fix-error.py?id=%s&fix=%s' target='hiddenIframe'>josm fix</a>"%(website, error_id, e[3])

        for (k, v) in e[0].items():
            html += "<div class='add'> + <b>" + k + "</b> = " + v + "<br></div>"
        for (k, v) in e[1].items():
            html += "<div class='mod'> ~ <b>" + k + "</b> = " + v + "<br></div>"
        for k in e[2]:
            html += "<div class='del'> - <b>" + k + "</b></div>"
        html += "</div>"

        html += "</div>"

    html += _("Error reported on: ") + " " + b_date.strftime("%Y-%m-%d")
    html += "</div>"

    ## bottom links
    html += "<div class=\"bulle_verif\">"
    html += "<a href=\"http://www.openstreetmap.org/?lat=%s&lon=%s&zoom=18\" target=\"_blank\">osmlink</a> "%(lat, lon)
    html += "<a href=\"http://www.openstreetmap.org/edit?lat=%s&lon=%s&zoom=18\" target=\"_blank\">potlatch</a> "%(lat, lon)
    minlat = float(lat) - 0.002
    maxlat = float(lat) + 0.002
    minlon = float(lon) - 0.002
    maxlon = float(lon) + 0.002
    html += "<a href=\"http://localhost:8111/load_and_zoom?left=%f&bottom=%f&right=%f&top=%f"%(minlon,minlat,maxlon,maxlat)
    if res["elems"]:
        html += "&select=" + res["elems"].replace("_",",")
    html += "\" target=\"hiddenIframe\">josm zone</a> "
    html += "</div>"
    html += "<div class=\"bulle_maj\">"
    html += "<b>%s :</b> " % _("change status")
    html += "<a onclick=\"setTimeout('pois.loadText();',2000);\" href=\"/cgi-bin/status.py?e=%s&s=done\" target=\"hiddenIframe\">%s</a> "%(error_id, _("corrected"))
    html += "<a onclick=\"setTimeout('pois.loadText();',2000);\" href=\"/cgi-bin/status.py?e=%s&s=false\" target=\"hiddenIframe\">%s</a> "%(error_id, _("false positive"))
    html += "</div>"
    
    ##
    ############################################################

    marker   = "markers/marker-b-%d.png" % (res["item"])
    print "\t".join([lat, lon, str(error_id), marker, "17,33", "-8,-33", html]).encode("utf8")
    
