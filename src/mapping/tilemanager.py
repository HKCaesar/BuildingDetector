import tileutils
from PIL import Image
from utils import urlopen_with_retry
import cStringIO
from storage.storagemanager import getStorageManager
import django.contrib.gis.geos.collections

class AbstractTileManager:
    def __init__(self):
        pass

    def get_tile(self, x, y):
        """must be implemented by subclass"""
        raise NotImplementedError

class BingTileManager(AbstractTileManager):
    def __init__(self):
        self.mt_counter = 0
        self.TILE_SIZE = 256
        self.mercator = tileutils.GlobalMercator()
        self.storagemanager = getStorageManager()

    ## Returns a template URL for the virtualEarth
    def layer_url_template(self, layer):
        layers_name = ["r", "a", "h"]
        return 'http://' + layers_name[layer] + \
               '%i.ortho.tiles.virtualearth.net/tiles/' + \
               layers_name[layer] + '%s.png?g=%i'

    ## Returns the URL to the virtualEarth tile
    def get_url(self, counter, coord, layer):
        version = 392
        return self.layer_url_template(layer) % (counter, coord, version)

    def get_tile(self, x, y, zoom):
        self.mt_counter += 1
        self.mt_counter = self.mt_counter % 4 #(count using 1-4 servers)

        gtx, gty        = self.mercator.GoogleTile(x, y, zoom)
        image_file      = self.storagemanager.get('bing_raw', "bing_%s_%s_%s_%s.png" % (zoom, gtx, gty, self.TILE_SIZE))

        if image_file is not None:
            return Image.open(cStringIO.StringIO(image_file))
        else:
            quad_key = self.mercator.QuadTree(x, y, zoom)

            url = self.get_url(self.mt_counter, quad_key, 1)
            f = urlopen_with_retry(url)
            image_file = f.read()
            self.storagemanager.put('bing_raw', "bing_%s_%s_%s_%s.png" % (zoom, gtx, gty, self.TILE_SIZE), image_file)
            return Image.open(cStringIO.StringIO(image_file))
            

class StaticMapGenerator:
    def __init__(self, li_zoom_levels, max_width = 1200, max_height = 1200, padding=0):
        self.MAX_MAP_WIDTH = max_width
        self.MAX_MAP_HEIGHT = max_height
        self.PADDING = padding
        self.mercator = tileutils.GlobalMercator()
        self.reset()
        self.set_tile_manager(BingTileManager(), li_zoom_levels)
        self.storagemanager = getStorageManager()

    def reset(self):
        self.lines = []
        self.markers = []
        self.polygons = []
        self.bbox = None
        self.ur_p_x = None
        self.ur_p_y = None
        self.ll_p_x = None
        self.ll_p_y = None
        self.ll_lat = None
        self.ll_long = None
        self.zoom = None
        self.image_width = None
        self.image_height = None
        self.TILE_SIZE = 256

    def set_tile_manager(self, tile_manager, li_zoom_levels):
        self.zoom_to_tile_manager = {}
        self.zoom_levels = []
        for zl in li_zoom_levels:
            self.zoom_to_tile_manager[zl] = tile_manager
        self.zoom_levels = self.zoom_to_tile_manager.keys()
        self.zoom_levels.sort()
        self.zoom_levels.reverse()

    def add_polygon(self, poly):
        self.polygons.append(poly)
        self.reset_bbox()
        self.reset_size_n_zoom()

    def add_line(self, line):
        self.lines.append(line)
        self.reset_bbox()
        self.reset_size_n_zoom()

    def add_marker(self, marker):
        self.markers.append(marker)
        self.reset_bbox()
        self.reset_size_n_zoom()

    def all_geoms(self):
        return self.lines + self.markers + self.polygons

    def reset_bbox(self):
        for geom in self.all_geoms():
            check_coords = geom.extent

            if not self.bbox:
                self.bbox = [[check_coords[0], check_coords[1]], [check_coords[2], check_coords[3]]]
                continue

            check_ll, check_ur = [[check_coords[0], check_coords[1]], [check_coords[2], check_coords[3]]]

            if check_ll[0] < self.bbox[0][0]:
                self.bbox[0][0] = check_ll[0]
            if check_ll[1] < self.bbox[0][1]:
                self.bbox[0][1] = check_ll[1]

            if check_ur[0] > self.bbox[1][0]:
                self.bbox[1][0] = check_ur[0]
            if check_ur[1] > self.bbox[1][1]:
                self.bbox[1][1] = check_ur[1]

    def reset_size_n_zoom(self):
        #convert the bounds in lat/long to bounds in meters
        ur_m_x, ur_m_y = self.mercator.LatLonToMeters(self.bbox[1][1], self.bbox[1][0])
        ll_m_x, ll_m_y = self.mercator.LatLonToMeters(self.bbox[0][1], self.bbox[0][0])

        #FIND A ZOOM LEVEL THAT CAN DISPLAY THE ENTIRE TRAIL AT THE DEFINED MAP SIZE
        for zoom in self.zoom_levels: #[17,16,15,14,13,12,11,10,9,8]:
            ur_p_x, ur_p_y = self.mercator.MetersToPixels(ur_m_x, ur_m_y, zoom)
            ll_p_x, ll_p_y = self.mercator.MetersToPixels(ll_m_x, ll_m_y, zoom)

            if ((ur_p_x - ll_p_x) < self.MAX_MAP_WIDTH) and ((ur_p_y - ll_p_y) < self.MAX_MAP_HEIGHT):
                break

        self.zoom = zoom
        self.ur_p_x = int(ur_p_x) + self.PADDING
        self.ur_p_y = int(ur_p_y) + self.PADDING
        self.ll_p_x = int(ll_p_x) - self.PADDING
        self.ll_p_y = int(ll_p_y) - self.PADDING

        ll_m_x, ll_m_y = self.mercator.PixelsToMeters(self.ll_p_x, self.ll_p_y, self.zoom)
        self.ll_lat, self.ll_long = self.mercator.MetersToLatLon(ll_m_x, ll_m_y)

        self.image_width = self.ur_p_x - self.ll_p_x
        self.image_height = self.ur_p_y - self.ll_p_y

    def x_y_for_lat_long(self, lat, lng):
        m_x, m_y = self.mercator.LatLonToMeters(lat, lng)
        p_x, p_y = self.mercator.MetersToPixels(m_x, m_y, self.zoom)
        rx = p_x - self.ll_p_x
        ry = self.ur_p_y - p_y
        return [rx, ry]

    def lat_long_for_x_y(self, rx, ry):
        p_y = self.ur_p_y - ry
        p_x = self.ll_p_x + rx
        m_x, m_y = self.mercator.PixelsToMeters(p_x, p_y, self.zoom)
        lat, long = self.mercator.MetersToLatLon(m_x, m_y)
        return [lat, long]
        
    def get_tile_image(self, tile_coords):

        self.reset()
        top_coord       = (tile_coords[0], tile_coords[1])
        bottom_coord    = (tile_coords[2], tile_coords[3])
        linestring      = django.contrib.gis.geos.collections.LineString((top_coord, bottom_coord))
        mlinestring     = django.contrib.gis.geos.collections.MultiLineString([linestring])
        
        self.add_line(mlinestring)

        filename        = ','.join(str(item) for item in tile_coords)
        
        tile_image_data         = self.storagemanager.get('bing_tiles', "%s.png" % (filename))
        if tile_image_data is None:
            tile_image          = self.generate_static_map()
            tile_image_bytes    = cStringIO.StringIO()
            tile_image.save(tile_image_bytes, 'PNG')
            self.storagemanager.put('bing_tiles', "%s.png" % (filename), tile_image_bytes.getvalue())
        else:
            tile_image          = Image.open(cStringIO.StringIO(tile_image_data))
            
        return tile_image

    def generate_static_map(self):
        
        image = Image.new("RGB", (self.image_width, self.image_height))

        start_tile_x, start_tile_y = self.mercator.PixelsToTile(self.ll_p_x, self.ll_p_y)

        start_tile_origin_x = start_tile_x * self.TILE_SIZE
        start_tile_origin_y = start_tile_y * self.TILE_SIZE

        #PASTE ALL BASEMAP TILES ON THE IMAGE
        curr_x = start_tile_origin_x
        while (curr_x <= (self.ur_p_x + self.TILE_SIZE)):

            curr_y = start_tile_origin_y
            while (curr_y <= (self.ur_p_y + self.TILE_SIZE)):
                tile = self.zoom_to_tile_manager[self.zoom].get_tile(curr_x / self.TILE_SIZE, curr_y / self.TILE_SIZE, self.zoom)

                pos_y = (self.ur_p_y - curr_y) - self.TILE_SIZE

                image.paste(tile, (curr_x - self.ll_p_x, pos_y))

                curr_y += self.TILE_SIZE

            curr_x += self.TILE_SIZE

        return image

    def coords_to_ltrb(self, coords, top = 0, left = 0, right = 0, bottom = 0, returnInt=False):
        for coord in coords:
            # Check x axis
            if coord[0] < left:
                left = coord[0]
            if coord[0] > right:
                right = coord[0]
            # Check y axis 
            if coord[1] < top:
                top = coord[1]
            if coord[1] > bottom:
                bottom = coord[1]

        if returnInt is True:
            return (int(left), int(top), int(right), int(bottom))

        return (left, top, right, bottom)