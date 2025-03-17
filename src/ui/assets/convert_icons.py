#!/usr/bin/env python3
import os
import cairosvg

def convert_svg_to_png(svg_path, png_path, size=24):
    """Convert an SVG file to PNG format.
    
    Args:
        svg_path: Path to the SVG file
        png_path: Path to save the PNG file
        size: Size of the PNG image (default: 24)
    """
    cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=size, output_height=size)

def main():
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icons_dir = os.path.join(script_dir, 'icons')
    
    # Create icons directory if it doesn't exist
    os.makedirs(icons_dir, exist_ok=True)
    
    # Get all SVG files in the icons directory
    svg_files = [f for f in os.listdir(icons_dir) if f.endswith('.svg')]
    
    # Convert each SVG file to PNG
    for svg_file in svg_files:
        svg_path = os.path.join(icons_dir, svg_file)
        png_file = svg_file.replace('.svg', '.png')
        png_path = os.path.join(icons_dir, png_file)
        
        print(f"Converting {svg_file} to {png_file}...")
        convert_svg_to_png(svg_path, png_path)
    
    print("Conversion complete!")

if __name__ == "__main__":
    main() 