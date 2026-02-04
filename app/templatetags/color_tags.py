from django import template

register = template.Library()

# Comprehensive color mapping for common color names to hex codes
COLOR_MAP = {
    # Reds & Pinks
    'red': '#FF0000',
    'light rose': '#FF69B4',
    'rose': '#FF007F',
    'pink': '#FFC0CB',
    'hot pink': '#FF1493',
    'deep pink': '#FF1493',
    'light pink': '#FFB6C1',
    'pale pink': '#FFDAB9',
    'crimson': '#DC143C',
    'dark red': '#8B0000',
    'dark crimson': '#8B0000',
    
    # Oranges
    'orange': '#FFA500',
    'dark orange': '#FF8C00',
    'light orange': '#FFE4B5',
    'coral': '#FF7F50',
    'salmon': '#FA8072',
    'light salmon': '#FFA07A',
    'tomato': '#FF6347',
    'tan': '#D2B48C',
    'peach': '#FFDAB9',
    
    # Yellows
    'yellow': '#FFFF00',
    'gold': '#FFD700',
    'khaki': '#F0E68C',
    'light yellow': '#FFFFE0',
    'pale yellow': '#FFFACD',
    'cream': '#FFFDD0',
    'beige': '#F5F5DC',
    
    # Greens
    'green': '#008000',
    'light green': '#90EE90',
    'lime': '#00FF00',
    'dark green': '#006400',
    'forest green': '#228B22',
    'olive': '#808000',
    'sea green': '#2E8B57',
    'teal': '#008080',
    'turquoise': '#40E0D0',
    'cyan': '#00FFFF',
    'mint': '#98FF98',
    
    # Blues
    'blue': '#0000FF',
    'light blue': '#ADD8E6',
    'dark blue': '#00008B',
    'navy': '#000080',
    'navy blue': '#000080',
    'sky blue': '#87CEEB',
    'deep sky blue': '#00BFFF',
    'royal blue': '#4169E1',
    'cornflower blue': '#6495ED',
    'powder blue': '#B0E0E6',
    'steel blue': '#4682B4',
    'slate blue': '#6A5ACD',
    'midnight blue': '#191970',
    'dodger blue': '#1E90FF',
    
    # Purples
    'purple': '#800080',
    'dark purple': '#663399',
    'indigo': '#4B0082',
    'violet': '#EE82EE',
    'plum': '#DDA0DD',
    'orchid': '#DA70D6',
    'medium purple': '#9370DB',
    'lavender': '#E6E6FA',
    'thistle': '#D8BFD8',
    'medium violet red': '#C71585',
    
    # Browns
    'brown': '#A52A2A',
    'dark brown': '#654321',
    'light brown': '#CD853F',
    'peru': '#CD853F',
    'tan': '#D2B48C',
    'chocolate': '#D2691E',
    'saddle brown': '#8B4513',
    'sienna': '#A0522D',
    'maroon': '#800000',
    
    # Neutrals
    'white': '#FFFFFF',
    'black': '#000000',
    'gray': '#808080',
    'grey': '#808080',
    'light gray': '#D3D3D3',
    'light grey': '#D3D3D3',
    'dark gray': '#A9A9A9',
    'dark grey': '#A9A9A9',
    'silver': '#C0C0C0',
    'gainsboro': '#DCDCDC',
    'white smoke': '#F5F5F5',
    'ghost white': '#F8F8FF',
    'dim gray': '#696969',
    'dim grey': '#696969',
    'lightgray': '#D3D3D3',
    'darkgray': '#A9A9A9',
}

@register.filter
def color_to_hex(color_name):
    """
    Convert a color name to its hex equivalent.
    Returns the hex code if found in COLOR_MAP.
    If the color is already a valid hex code, returns it as-is.
    If the color name is not found, returns a default white color (#FFFFFF).
    """
    if not color_name:
        return "#FFFFFF"  # Default gray for empty values
    
    color_str = str(color_name).strip()
    
    # If it's already a hex color, return it as-is
    if color_str.startswith('#') and len(color_str) in [4, 7]:
        return color_str
    
    # Convert to lowercase and look up in the map
    color_lower = color_str.lower()
    
    # Return mapped color or default gray if not found
    return COLOR_MAP.get(color_lower, '#FFFFFF')
