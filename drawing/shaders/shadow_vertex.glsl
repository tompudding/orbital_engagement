#version 130
uniform vec3 sb_dimensions;
in vec3 vertex_data;

void main()
{
    gl_Position = vec4( ((vertex_data.x*2)/sb_dimensions.x)-1,
                        ((vertex_data.y*2)/sb_dimensions.y)-1,
                        -vertex_data.y/sb_dimensions.y,
                        1);
    //gl_Position = vec4( vertex_data.x, vertex_data.y, 0, 1);
}
