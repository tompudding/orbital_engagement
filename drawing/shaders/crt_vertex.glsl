#version 130

uniform vec3 screen_dimensions;
uniform vec2 translation;
uniform vec2 scale;
in vec3 vertex_data;
in vec2 tc_data;

out vec2 texcoord;

void main()
{
    gl_Position = vec4( (((vertex_data.x)*2)/screen_dimensions.x)-1,
                        (((vertex_data.y)*2)/screen_dimensions.y)-1,
                        -vertex_data.z/screen_dimensions.z,
                        1.0) ;
    texcoord    = tc_data;
}
