"""Lossless nearest-neighbour OCR crops; original images remain immutable."""
from pathlib import Path
import struct,zlib
from fish_proteus.waveform import _png_rgb


def crop_scaled_png(source,destination,box,scale=3):
    width,height,rows=_png_rgb(Path(source).read_bytes())
    x0,y0,x1,y1=map(int,box)
    if not (0<=x0<x1<=width and 0<=y0<y1<=height and 1<=scale<=4):
        raise ValueError('OCR crop is outside the source image')
    output=[]
    for y in range(y0,y1):
        row=rows[y][x0*3:x1*3]
        expanded=b''.join(row[x:x+3]*scale for x in range(0,len(row),3))
        output.extend([b'\0'+expanded]*scale)
    def chunk(kind,payload):
        return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)
    data=(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',(x1-x0)*scale,(y1-y0)*scale,8,2,0,0,0))
          +chunk(b'IDAT',zlib.compress(b''.join(output)))+chunk(b'IEND',b''))
    Path(destination).write_bytes(data)
    return {'source_box':list(box),'scale':scale,'output_size':[(x1-x0)*scale,(y1-y0)*scale]}
