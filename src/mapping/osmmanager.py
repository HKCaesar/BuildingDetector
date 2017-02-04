from utils import urlopen_with_retry
import xml.etree.cElementTree as ET
import django.contrib.gis.geos.collections

class OSMManager():

    # Get the raw building data from OSM
    def getBuildingData(self, left, right, top, bottom):

        response        = urlopen_with_retry("http://www.openstreetmap.org/api/0.6/map?bbox=%s,%s,%s,%s" % (left, right, top, bottom))
        response_data   = response.read()

        xml_data =  ET.fromstring(response_data)
        return self._processBuildingData(xml_data)

    # Reformats the existing building data from OSM so we can use it
    def _processBuildingData(self, building_data):

        polygons = []

        for abuilding in building_data.findall("way/tag[@k='building'][@v='yes']/.."):
            coords = []
            refs = {}
            for aref in abuilding.findall('nd'):

                # Some token caching
                if aref.get('ref') in refs:
                    coords.append(refs[aref.get('ref')])
                    continue                    
                
                anode = building_data.find("./node[@id='%s'][@visible='true']/." % (aref.get('ref')))
                coords.append((float(anode.get('lon')), float(anode.get('lat'))))
                refs[aref.get('ref')] = (float(anode.get('lon')), float(anode.get('lat')))


            if str(coords[0]) != str(coords[-1]):
                coords.append(coords[0])

            if len(coords) > 3:
                mpolygon = django.contrib.gis.geos.collections.Polygon(tuple(coords))
                polygons.append(mpolygon)

        return polygons

    # Generates a JOSM compatible output file containing the newly detected buildings
    def generateOutputXml(self, minlat, minlon, maxlat, maxlon, building_coords):

        id_count = 0
        
        osm = ET.Element('osm', {'version': '0.6'})
        ET.SubElement(osm, 'bounds', {
            'minlat': str(minlat),
            'minlon': str(minlon),
            'maxlat': str(maxlat),
            'maxlon': str(maxlon)
            })

        for building in building_coords:

            id_count = id_count - 1
            
            way = ET.SubElement(osm, 'way', {
                'id'        : str(id_count), 
                'visible'   : 'true', 
                'action'    : 'modify'
                })
            ET.SubElement(way, 'tag', {'k': 'building', 'v': 'yes'})

            first_node_id = id_count - 1
            
            for coords in building:
                
                id_count = id_count - 1
                
                node = ET.SubElement(osm, 'node', {
                    'id'        : str(id_count), 
                    'action'    : 'modify', 
                    'visible'   : 'true',
                    'lat'       : str(coords[0]),
                    'lon'       : str(coords[1])
                    })
                ET.SubElement(way, 'nd', {'ref': str(id_count)})
            
            ET.SubElement(way, 'nd', {'ref': str(first_node_id)})

        return ET.tostring(osm)
