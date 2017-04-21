# Copyright (C) 2008, One Laptop per Child
# Author: Keshav Sharma <keshav7890@gmail.com> & Vaibhav Sharma
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

from __future__ import division
import pygtk
import gtk
from gtk import gdk
import gobject
import sys
from PIL import Image,ImageEnhance,ImageFont,ImageFilter,ImageOps,ImageDraw

import StringIO
import logging
import random
from sugar import mime
import gst, pygame, sys, time
from random import *

class ImageProcessor(gtk.DrawingArea):
    __gsignals__ = {
        'expose-event' : ('override'),
        'zoom-changed' : (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, []),
        'angle-changed': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, []),
                   }

    __gproperties__ = {
        'zoom': (gobject.TYPE_FLOAT, 'Zoom Factor', 'Factor of zoom',0, 4, 1, gobject.PARAM_READWRITE),
        'angle': (gobject.TYPE_INT, 'Angle', 'Angle of rotation',0, 360, 0, gobject.PARAM_READWRITE),
        'file_location':( gobject.TYPE_STRING, 'File Location', 'Location of the image file',
        '', gobject.PARAM_READWRITE),
        }
  
    def __init__(self):
        gtk.DrawingArea.__init__(self)
        self.set_app_paintable(True)
        self.undo                = None
        self.redo                = None
        self.save                = None
        self.pixbuf              = None
        self.zoom                = None
        self.input_text          = "text to edit"
        self._tempfile           = None
        self.file_location       = None
        self._temp_pixbuf        = None
        self.edit_text           = None
        self.im                  = None
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True
        self.angle = 0

    def do_get_property(self, pspec):
        if pspec.name == 'zoom'          :    return self.zoom
        elif pspec.name == 'angle'       :    return self.angle
        elif pspec.name == 'file_location':   return self.file_location
        else:            raise AttributeError('unknown property %s' % pspec.name)

    def do_set_property(self, pspec, value):
        if pspec.name == 'zoom':            self.set_zoom(value)
        elif pspec.name == 'angle':            self.set_angle(value)
        elif pspec.name == 'file_location'  :      self.set_file_location(value)
        else:        raise AttributeError('unknown property %s' % pspec.name)

    def calculate_optimal_zoom(self, width=None, height=None, pixbuf=None):
        # This tries to figure out a best fit model
        # If the image can fit in, we show it in 1:1,
        # in any other case we show it in a fit to screen way

        if pixbuf == None:
            pixbuf = self.pixbuf

        if width == None or height == None:
            rect = self.parent.get_allocation()
            width = rect.width
            height = rect.height

        if width < pixbuf.get_width() or height < pixbuf.get_height():
            # Image is larger than allocated size
            zoom = min(width / pixbuf.get_width(),
                    height / pixbuf.get_height())
        else:            zoom = 1

        self._optimal_zoom_flag = True

        return zoom - 0.018 #XXX: Hack

    def set_pixbuf( self , pixbuf ):
        self.pixbuf              = pixbuf
        self.zoom                = None
        self._image_changed_flag = True
        if self.window:
            alloc       = self.get_allocation()
            rect        = gdk.Rectangle( alloc.x , alloc.y , alloc.width ,alloc.height )
            self.window.invalidate_rect( rect , True )
            self.window.process_updates( True )

    #def do_size_request(self, requisition):
    #    requisition.width = self.pixbuf.get_width()
    #    requisition.height = self.pixbuf.get_height()

    def do_expose_event(self, event):
        ctx = self.window.cairo_create()
        ctx.rectangle(event.area.x, event.area.y,
            event.area.width, event.area.height)
        ctx.clip()
        self.draw(ctx)

    def draw(self, ctx):
        if not self.pixbuf:
            return
        if self.zoom == None:
            self.zoom = self.calculate_optimal_zoom()

        if self._temp_pixbuf == None or self._image_changed_flag == True:
            width, height = self.rotate()
            self._temp_pixbuf = self._temp_pixbuf.scale_simple(width, height, gtk.gdk.INTERP_TILES)
            self._image_changed_flag = False

        rect = self.get_allocation()
        x = rect.x
        y = rect.y

        width = self._temp_pixbuf.get_width()
        height = self._temp_pixbuf.get_height()

        if self.parent:
            rect = self.parent.get_allocation()
            if rect.width > width:
                x = int(((rect.width - x) - width) / 2)

            if rect.height > height:
                y = int(((rect.height - y) - height) / 2)

        self.set_size_request(self._temp_pixbuf.get_width(),
                self._temp_pixbuf.get_height())

        ctx.set_source_pixbuf(self._temp_pixbuf, x, y)

        ctx.paint()

    def set_zoom(self, zoom):
        self._image_changed_flag = True
        self._optimal_zoom_flag = False
        self.zoom = zoom

        if self.window:
            alloc = self.get_allocation()
            rect = gdk.Rectangle(alloc.x, alloc.y,alloc.width, alloc.height)
            self.window.invalidate_rect(rect, True)
            self.window.process_updates(True)

        self.emit('zoom-changed')

    def set_angle(self, angle):
        self._image_changed_flag = True
        self._optimal_zoom_flag = True

        self.angle = angle

        if self.window:
            alloc = self.get_allocation()
            rect = gdk.Rectangle(alloc.x, alloc.y,
                alloc.width, alloc.height)
            self.window.invalidate_rect(rect, True)
            self.window.process_updates(True)

        self.emit('angle-changed')

    def rotate(self):
        if self.angle == 0:
            rotate = gtk.gdk.PIXBUF_ROTATE_NONE
        elif self.angle == 90:
            rotate = gtk.gdk.PIXBUF_ROTATE_COUNTERCLOCKWISE
        elif self.angle == 180:
            rotate = gtk.gdk.PIXBUF_ROTATE_UPSIDEDOWN
        elif self.angle == 270:
            rotate = gtk.gdk.PIXBUF_ROTATE_CLOCKWISE
        elif self.angle == 360:
            self.angle = 0
            rotate = gtk.gdk.PIXBUF_ROTATE_NONE
        else:
            logging.warning('Got unsupported rotate angle')

        self._temp_pixbuf = self.pixbuf.rotate_simple(rotate)
        width = int(self._temp_pixbuf.get_width() * self.zoom)
        height = int(self._temp_pixbuf.get_height() * self.zoom)

        return (width, height)

    def zoom_in(self):
        self.set_zoom(self.zoom + 0.2)
        if self.zoom > (4):            return False
        else:            return True

    def zoom_out(self):
        self.set_zoom(self.zoom - 0.2)
        if self.zoom <= 0.2:            return False
        else:            return True

    def grey(self,value):
        pixbuf = self.pixbuf
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True
        if self.window:
            im = self.pixbuftoImage(pixbuf)
            self.undo=im.copy()
            im.convert("RGB")
            r, g, b = im.split()
            im = Image.merge("RGB", (g,g,g))
            self.redo=im.copy()
            pix=self.imagetopixbuf(im)            
            self.set_pixbuf( pix )
            self.window.process_updates( True )

    def image_undo(self):
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True
        if self.window:
            pix=self.imagetopixbuf(self.undo)
            self.set_pixbuf( pix )
            self.window.process_updates( True )
            
            
    def image_redo(self):
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True
        if self.window:
            pix=self.imagetopixbuf(self.redo)
            self.set_pixbuf( pix )
            self.window.process_updates( True )
    def image_save(self):
        pixbuf=self.pixbuf
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True
        if self.window:
            pix=self.pixbuftoImage(pixbuf)
            self.save=pix.copy()
    def image_paste(self):
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True
        if self.window:
            pix=self.imagetopixbuf(self.save)
            self.set_pixbuf( pix )
            self.window.process_updates( True )
            

    def image_Blur(self,value):
        pixbuf = self.pixbuf
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True
        if self.window:
            im = self.pixbuftoImage(pixbuf)
            self.undo=im.copy()
            im = im.filter(ImageFilter.BLUR)
            self.redo=im.copy()
            pix=self.imagetopixbuf(im)
            self.set_pixbuf( pix )
            self.window.process_updates( True )


    def image_Transpose(self,value):
        pixbuf = self.pixbuf
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True
        if self.window:
            im = self.pixbuftoImage(pixbuf)
            self.undo=im.copy()
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
            self.redo=im.copy()
            pix=self.imagetopixbuf(im)
            self.set_pixbuf( pix )
            self.window.process_updates( True )


    def image_Offset(self,value):
        pixbuf = self.pixbuf
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True
        if self.window:
            im = self.pixbuftoImage(pixbuf)
            self.undo=im.copy()
            w,h=im.size
            im = im.offset(w/2,h/2)
            self.redo=im.copy()
            pix=self.imagetopixbuf(im)
            self.set_pixbuf( pix )
            self.window.process_updates( True )


    def image_Contour(self,value):
        pixbuf = self.pixbuf
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True
        if self.window:
            im = self.pixbuftoImage(pixbuf)
            self.undo=im.copy()
            im = im.filter(ImageFilter.CONTOUR)
            self.redo=im.copy()
            pix=self.imagetopixbuf(im)
            self.set_pixbuf( pix )
            self.window.process_updates( True )


    def image_Finedges(self,value):
        pixbuf = self.pixbuf
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True
        if self.window:
            im = self.pixbuftoImage(pixbuf)
            self.undo=im.copy()
            im = im.filter(ImageFilter.FIND_EDGES)
            self.redo=im.copy()
            pix=self.imagetopixbuf(im)
            self.set_pixbuf( pix )
            self.window.process_updates( True )


    def image_Solarize(self,value):
        pixbuf = self.pixbuf
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True
        if self.window:
            im = self.pixbuftoImage(pixbuf)
            self.undo=im.copy()
            im = ImageOps.solarize(im, threshold=128)
            self.redo=im.copy()
            pix=self.imagetopixbuf(im)
            self.set_pixbuf( pix )
            self.window.process_updates( True )
    def pil_to_pixbuf(self,image):
        """Return a pixbuf created from the PIL <image>."""
        imagestr = image.tostring()
        IS_RGBA = image.mode == 'RGBA'
        return gtk.gdk.pixbuf_new_from_data(imagestr, gtk.gdk.COLORSPACE_RGB, IS_RGBA, 8, image.size[0], image.size[1], (IS_RGBA and 4 or 3) * image.size[0])

    def pixbuf_to_pil(self,pixbuf):
        """Return a PIL image created from <pixbuf>."""
        dimensions = pixbuf.get_width(), pixbuf.get_height()
        stride = pixbuf.get_rowstride()
        pixels = pixbuf.get_pixels()
        mode = pixbuf.get_has_alpha() and 'RGBA' or 'RGB'
        return Image.frombuffer(mode, dimensions, pixels, 'raw', mode, stride, 1)

    def image_contrast(self,value):
        pixbuf = self.pixbuf
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True
        if self.window:
            im = self.pixbuftoImage(pixbuf)
            self.undo=im.copy()
            pixbuf=self.imagetopixbuf(im)
            im = self.pixbuf_to_pil(pixbuf)
            im = ImageEnhance.Contrast(im).enhance(1.2)
            pix=self.pil_to_pixbuf(im)
            im = self.pixbuftoImage(pix)
            self.redo=im.copy()
            pix=self.imagetopixbuf(im)
            self.set_pixbuf( pix )
            self.window.process_updates( True )


    def image_bright(self,value):
        pixbuf = self.pixbuf
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True
        if self.window:
            im = self.pixbuftoImage(pixbuf)
            self.undo=im.copy()
            pixbuf=self.imagetopixbuf(im)
            im = self.pixbuf_to_pil(pixbuf)

            im = ImageEnhance.Brightness(im).enhance(1.2)
            pix=self.pil_to_pixbuf(im)
            im = self.pixbuftoImage(pix)
            self.redo=im.copy()
            pix=self.imagetopixbuf(im)
            self.set_pixbuf( pix )
            self.window.process_updates( True )

    def image_dcontrast(self,value):
        pixbuf = self.pixbuf
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True
        if self.window:
            im = self.pixbuftoImage(pixbuf)
            self.undo=im.copy()
            pixbuf=self.imagetopixbuf(im)
            im = self.pixbuf_to_pil(pixbuf)
            im = ImageEnhance.Contrast(im).enhance(0.8)
            pix=self.pil_to_pixbuf(im)
            im = self.pixbuftoImage(pix)
            self.redo=im.copy()
            pix=self.imagetopixbuf(im)
            self.set_pixbuf( pix )
            self.window.process_updates( True )

    def image_dbright(self,value):
        pixbuf = self.pixbuf
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True
        if self.window:
            im = self.pixbuftoImage(pixbuf)
            self.undo=im.copy()
            pixbuf=self.imagetopixbuf(im)
            im = self.pixbuf_to_pil(pixbuf)
            im = ImageEnhance.Brightness(im).enhance(0.8)
            pix=self.pil_to_pixbuf(im)
            im = self.pixbuftoImage(pix)
            self.redo=im.copy()
            pix=self.imagetopixbuf(im)
            self.set_pixbuf( pix )
            self.window.process_updates( True )


    def image_left_top(self,edit_text):
        self.edit_text="left_top"        
        self.image_edit_text(self.edit_text)

    def image_right_top(self,edit_text):
        self.edit_text='right_top'
        self.image_edit_text(self.edit_text)

    def image_left_bottom(self,edit_text):
        self.edit_text='left_bottom'
        self.image_edit_text(self.edit_text)

    def image_right_bottom(self,edit_text):
        self.edit_text='right_bottom' 
        self.image_edit_text(self.edit_text)

    def image_edit_text(self,edit_text):
        pixbuf = self.pixbuf
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True
        self.edit_text = edit_text
        if self.window:
            im = self.pixbuftoImage(pixbuf)
            self.undo=im.copy()
            out=self.Imprint(im, self.input_text,self.edit_text)
            self.redo=out.copy()
            pix=self.imagetopixbuf(out)
            self.set_pixbuf( pix )
            self.window.process_updates( True )
    
    def input_text_cb(self,text):
        self.input_text=str(text)

    def Imprint(self,im, inputtext,edit_text, font=None, color=None, opacity=.6, margin=(30,30)): 
        """ 
        imprints a PIL image with the indicated text in lower-right corner 
        """ 
        if im.mode != "RGBA": 
           im = im.convert("RGBA") 
        w,h=im.size
        textlayer = Image.new("RGBA", im.size, (0,0,0,0)) 
        textdraw = ImageDraw.Draw(textlayer)
        textsize = textdraw.textsize(inputtext, font=font) 
        if edit_text=="left_top":
              textpos = [margin[i] for i in [0,1]] 
        elif edit_text=="right_top":
              textpos = im.size[0]-textsize[0]-margin[0],margin[1]
        elif edit_text=="left_bottom":
              textpos = margin[0],im.size[1]-textsize[1]-margin[1]
        else:
             textpos = [im.size[i]-textsize[i]-margin[i] for i in [0,1]] 
        textdraw.text(textpos, inputtext, font=font, fill="red") 
        if opacity != 1: 
            textlayer = self.reduce_opacity(textlayer,opacity) 
        return Image.composite(textlayer, im, textlayer) 

    def image_Sharpen(self,value):
        pixbuf = self.pixbuf
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True
        if self.window:
            im = self.pixbuftoImage(pixbuf)
            self.undo=im.copy()
            im = im.filter(ImageFilter.SHARPEN)
            self.redo=im.copy()
            pix=self.imagetopixbuf(im)
            self.set_pixbuf( pix )
            self.window.process_updates( True )


    def image_Ambross(self,value):
        pixbuf = self.pixbuf
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True
        if self.window:
            im = self.pixbuftoImage(pixbuf)
            self.undo=im.copy()
            im = im.filter(ImageFilter.EMBOSS)
            self.redo=im.copy()
            pix=self.imagetopixbuf(im)
            self.set_pixbuf( pix )
            self.window.process_updates( True )


    def image_Invert(self,value):
        pixbuf = self.pixbuf
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True
        if self.window:
            im = self.pixbuftoImage(pixbuf)
            self.undo=im.copy()
            im = ImageOps.invert(im)
            self.redo=im.copy()
            pix=self.imagetopixbuf(im)
            self.set_pixbuf( pix )
            self.window.process_updates( True )



    def image_Watermark(self,mark,pos):
        pixbuf = self.pixbuf
        self._image_changed_flag = True
        self._optimal_zoom_flag  = True

        if self.window:
            im1=Image.open(mark)
            im = self.pixbuftoImage(pixbuf)
            self.undo=im.copy()
            if pos=="tile":
                 im = self.watermark(im, im1,"tile",0.5)
            elif pos=="scale":
                 im = self.watermark(im, im1,"scale",0.5)
            else :#if pos is top_left
               im = self.watermark(im, im1,(0,0),0.5)
            #(raw_input('type of watermark(tile/scale,(xsize,ysize))')), 0.5)
            self.redo=im.copy()
            pix=self.imagetopixbuf(im)
            self.set_pixbuf( pix )
            self.window.process_updates( True )


    def pixbuftoImage(self,pb):
        width,height = pb.get_width(),pb.get_height()
        return Image.fromstring("RGB",(width,height),pb.get_pixels() )
    
    def imagetopixbuf(self,im):  
        file1 = StringIO.StringIO()  
        im.save(file1, "ppm")  
        contents = file1.getvalue()  
        file1.close()  
        loader = gtk.gdk.PixbufLoader("pnm")  
        loader.write(contents, len(contents))  
        pixbuf = loader.get_pixbuf()  
        loader.close()  
        return pixbuf        

    def reduce_opacity(self,im, opacity):
        """Returns an image with reduced opacity."""
        assert opacity >= 0 and opacity <= 1
        if im.mode != 'RGBA':        im = im.convert('RGBA')
        else                :        im = im.copy()
        alpha = im.split()[3]
        alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
        im.putalpha(alpha)
        return im
        #watermark to an image
    def watermark(self,im, mark, position, opacity=1):
        """Adds a watermark to an image."""
        if opacity < 1      :        mark = self.reduce_opacity(mark, opacity)
        if im.mode != 'RGBA':        im = im.convert('RGBA')
        # create a transparent layer the size of the image and draw the
        # watermark in that layer.
        layer = Image.new('RGBA', im.size, (0,0,0,0))
        if position == 'tile':
            w,h=im.size
            mark = mark.resize((w/2, h/2))
            for y in range(0, im.size[1], mark.size[1]):
                for x in range(0, im.size[0], mark.size[0]): layer.paste(mark,(x, y))
        elif position == 'scale':
            # scale, but preserve the aspect ratio
            ratio = min(float(im.size[0]) / mark.size[0], float(im.size[1]) / mark.size[1])
            w = int(mark.size[0] * ratio)
            h = int(mark.size[1] * ratio)
            mark = mark.resize((w, h))
            layer.paste(mark, ((im.size[0] - w) / 2, (im.size[1] - h) / 2))
        else:        
             w,h=im.size
             mark = mark.resize((w/2, h/2))
             layer.paste(mark, position)
        # composite the watermark with the layer
        return Image.composite(layer, im, layer)

    def original_cb(self,value):
        self.set_file_location(self.original)

    def set_file_location(self, file_location):
        self.original=file_location
        self.pixbuf = gtk.gdk.pixbuf_new_from_file(file_location)
        self.file_location = file_location
        self.zoom = None
        self._image_changed_flag = True
        if self.window:
            alloc = self.get_allocation()
            rect = gdk.Rectangle(alloc.x, alloc.y, alloc.width, alloc.height)
            self.window.invalidate_rect(rect, True)
            self.window.process_updates(True)

    def save_cb(self,file_path):
        pixbuf=self.pixbuf 
        pixbuf.save(file_path, 'png', {})
        
#check working of functions
def update(view_object):
    view.grey("g")
    return True


if __name__ == '__main__':
    window = gtk.Window()

    vadj = gtk.Adjustment()
    hadj = gtk.Adjustment()
    sw = gtk.ScrolledWindow(hadj, vadj)

    view = ImageProcessor()

    view.set_file_location(sys.argv[1])


    sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)


    sw.add_with_viewport(view)
    window.add(sw)

    window.set_size_request(800, 600)

    window.show_all()

    gobject.timeout_add(1000, update, view)

    gtk.main()
