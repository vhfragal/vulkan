struct Uniforms {
    screen_size: vec2<f32>,
};

@group(0) @binding(0) var<uniform> uniforms: Uniforms;
@group(0) @binding(1) var atlas_tex: texture_2d<f32>;
@group(0) @binding(2) var atlas_samp: sampler;

struct InstanceInput {
    @location(0) rect: vec4<f32>,   // x, y, w, h in screen pixels
    @location(1) uv_rect: vec4<f32>,// u0, v0, u1, v1 in [0..1]
    @location(2) color: vec4<f32>,  // tint / RGBA multiplier
};

struct VertexOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) uv: vec2<f32>,
    @location(1) color: vec4<f32>,
};

@vertex
fn vs_main(
    @builtin(vertex_index) v_idx: u32,
    inst: InstanceInput,
) -> VertexOut {
    // 2 triangles forming a unit quad [0..1]
    var corners = array<vec2<f32>, 6>(
        vec2<f32>(0.0, 0.0), vec2<f32>(1.0, 0.0), vec2<f32>(1.0, 1.0),
        vec2<f32>(0.0, 0.0), vec2<f32>(1.0, 1.0), vec2<f32>(0.0, 1.0)
    );

    let c = corners[v_idx];
    let pixel_pos = inst.rect.xy + c * inst.rect.zw;

    // Convert pixel coordinates [0..width, 0..height] -> NDC [-1..1, 1..-1]
    let ndc_x = (pixel_pos.x / uniforms.screen_size.x) * 2.0 - 1.0;
    let ndc_y = 1.0 - (pixel_pos.y / uniforms.screen_size.y) * 2.0;

    var out: VertexOut;
    out.pos = vec4<f32>(ndc_x, ndc_y, 0.0, 1.0);
    out.uv = mix(inst.uv_rect.xy, inst.uv_rect.zw, c);
    out.color = inst.color;
    return out;
}

@fragment
fn fs_main(in: VertexOut) -> @location(0) vec4<f32> {
    let texel = textureSample(atlas_tex, atlas_samp, in.uv);
    return texel * in.color;
}
