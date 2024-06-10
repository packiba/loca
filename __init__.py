import bpy
from bpy.types import Operator, Panel, PropertyGroup
from bpy.props import IntProperty, EnumProperty, BoolProperty, PointerProperty
from bpy.utils import register_class, unregister_class

bl_info = {
    "name": "loca",
    "author": "Pavel Kiba",
    "version": (1, 2, 0),
    "blender": (4, 1, 0),
    "location": "View3D > N-Panel > Animation",
    "description": "Create bone locators for animation",
    "warning": "",
    "doc_url": "",
    "category": "Animation",
}

axes = [
    ('TRACK_X', 'X', 'Select X', 0),
    ('TRACK_Y', 'Y', 'Select Y', 2),
    ('TRACK_Z', 'Z', 'Select Z', 4),
    ('TRACK_NEGATIVE_X', '-X', 'Select -X', 1),
    ('TRACK_NEGATIVE_Y', '-Y', 'Select -Y', 3),
    ('TRACK_NEGATIVE_Z', '-Z', 'Select -Z', 5),
]

global locators_RT_name_list
locators_RT_name_list = []

def show_message_box(message="", ttl="Message Box", ic='INFO'):
    def draw(self, context):
        self.layout.label(text=message)
    bpy.context.window_manager.popup_menu(draw, title=ttl, icon=ic)

def hide_scale_fcurves(armature_name, bone_name='_LOCA'):
    if bpy.data.objects[armature_name].animation_data.action:
        for fcurve in bpy.data.objects[armature_name].animation_data.action.fcurves:
            if '_LOCA' in fcurve.data_path or bone_name in fcurve.data_path:
                if 'scale' in fcurve.data_path:
                    fcurve.hide = True

class locaProps(PropertyGroup):
    axis: EnumProperty(
        name="Bone Axis",
        items=axes,
        description="Select local axis for rotation target",
        default="TRACK_Y",
    )
    select_axis: BoolProperty(
        name="Select Axis",
        description="Select local axis for rotation target",
        default=False,
    )
    locator_positioning: BoolProperty(
        name="Locator Positioning",
        description="Locator is positioning",
        default=False,
    )
    without_baking: BoolProperty(
        name="Without Baking",
        description="Locator without baking",
        default=False,
    )
    baking_frame_range: BoolProperty(
        name="Baking in Frame Range",
        description="Baking in frame range",
        default=True,
    )
    bake_start_fr: IntProperty(
        name="Start",
        description="Baking start frame",
        default=1,
    )
    bake_end_fr: IntProperty(
        name="End",
        description="Baking end frame",
        default=1,
    )

class Loca_OT_get_preview_range(Operator):
    bl_idname = "scene.get_preview_range"
    bl_label = "Get Preview Range"
    bl_description = "Get start and end frame from preview range"
    
    def execute(self, context):
        scene = context.scene
        props = scene.loca
        props.bake_start_fr = scene.frame_preview_start
        props.bake_end_fr = scene.frame_preview_end
        self.report({'INFO'}, f"Preview Range: Start = {props.bake_start_fr}, End = {props.bake_end_fr}")
        return {'FINISHED'}

class Loca_OT_create_locators(Operator):
    """Create locators"""
    bl_label = 'Create Locators'
    bl_idname = 'bones.locators'
    bl_options = {'REGISTER', 'UNDO'}

    rt_mode: BoolProperty(
        name="Rotation Target Mode",
        description="Switch to rotation target mode",
        default=False,
    )

    def create_widget(self, current_armature):
        widget_obj_name = 'wgt_loca'
        if widget_obj_name in bpy.data.objects:
            return
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.empty_add()
        bpy.context.object.name = widget_obj_name
        bpy.context.object.hide_viewport = True
        bpy.context.view_layer.objects.active = current_armature
        bpy.ops.object.mode_set(mode='POSE')

    def create_locator(self, context, bone_P, props):
        armature = context.active_object
        st_frame = props.bake_start_fr
        end_frame = props.bake_end_fr

        locator_name = f'{bone_P.name}_LOCA_RT' if self.rt_mode else f'{bone_P.name}_LOCA'
        bpy.ops.object.mode_set(mode='EDIT')
        source_E = armature.data.edit_bones[bone_P.name]
        locator_E = armature.data.edit_bones.new(locator_name)
        locator_E.head = source_E.head
        locator_E.tail = source_E.tail
        locator_E.matrix = source_E.matrix
        bpy.ops.object.mode_set(mode='POSE')
        locator_P = context.object.pose.bones[locator_name]
        locator_P.custom_shape = bpy.data.objects["wgt_loca"]
        context.object.data.bones.active = locator_P.bone
        copy_transforms = locator_P.constraints.new('COPY_TRANSFORMS')
        copy_transforms.target = armature
        copy_transforms.subtarget = bone_P.name

        if self.rt_mode:
            locators_RT_name_list.append(locator_name)
            bpy.ops.pose.visual_transform_apply()
            locator_P.constraints.remove(copy_transforms)
            props.locator_positioning = True
            bpy.ops.pose.select_all(action='DESELECT')
            locator_P.bone.select = True
            show_message_box(
                'Choose position for locator and press button "Positioning completed"', 'LOCATOR POSITIONING')
        else:
            if props.without_baking:
                bpy.ops.pose.visual_transform_apply()
                locator_P.constraints.remove(copy_transforms)
                child_of = locator_P.constraints.new('CHILD_OF')
                child_of.target = armature
                child_of.subtarget = bone_P.name
            else:
                bpy.ops.pose.select_all(action='DESELECT')
                locator_P.bone.select = True
                bpy.ops.anim.keyframe_insert_menu(type='Location')
                bpy.ops.nla.bake(frame_start=st_frame, frame_end=end_frame, only_selected=True,
                                 visual_keying=True, clear_constraints=True, use_current_action=True, bake_types={'POSE'})
                if locator_P.constraints:
                    locator_P.constraints.remove(locator_P.constraints[0])
                hide_scale_fcurves(armature.name)
                copy_transforms = bone_P.constraints.new('COPY_TRANSFORMS')
                copy_transforms.name = 'Copy locator transforms__Loca'
                copy_transforms.target = armature
                copy_transforms.subtarget = locator_name

    @classmethod
    def poll(cls, context):
        return context.selected_pose_bones is not None

    def execute(self, context):
        props = context.scene.loca
        armature = context.active_object
        props.locator_positioning = False
        sel_bones = context.selected_pose_bones
        if not context.scene.objects.get('wgt_loca'):
            self.create_widget(armature)
        for bone in sel_bones:
            self.create_locator(context, bone, props)
        return {'FINISHED'}

class Loca_OT_create_locators_RT(Operator):
    """Create locators for rotation target"""
    bl_label = 'Create Locators RT'
    bl_idname = 'bones.locators_rt'
    bl_options = {'REGISTER', 'UNDO'}

    def bake_locator(self, context, loc_name):
        armature = context.active_object
        props = context.scene.loca
        st_frame = props.bake_start_fr
        end_frame = props.bake_end_fr
        bone_name = loc_name.split('_LOCA')[0]
        locator_P = context.object.pose.bones[loc_name]
        context.object.data.bones.active = locator_P.bone
        pose_bone = context.object.pose.bones[bone_name]

        child_of = locator_P.constraints.new('CHILD_OF')
        child_of.target = armature
        child_of.subtarget = bone_name

        if props.without_baking:
            bpy.ops.pose.visual_transform_apply()
            locator_P.constraints.remove(child_of)
            child_of = locator_P.constraints.new('CHILD_OF')
            child_of.target = armature
            child_of.subtarget = bone_name
        else:
            bpy.ops.pose.select_all(action='DESELECT')
            locator_P.bone.select = True
            bpy.ops.anim.keyframe_insert_menu(type='Location')
            bpy.ops.nla.bake(frame_start=st_frame, frame_end=end_frame, only_selected=True,
                             visual_keying=True, clear_constraints=True, use_current_action=True, bake_types={'POSE'})
            if locator_P.constraints:
                locator_P.constraints.remove(locator_P.constraints[0])

            hide_scale_fcurves(armature.name)
            bpy.ops.pose.select_all(action='DESELECT')
            pose_bone.bone.select = True
            damped_track = pose_bone.constraints.new('DAMPED_TRACK')
            damped_track.name = 'Damped Track to locator__Loca'
            damped_track.target = armature
            damped_track.subtarget = loc_name
            damped_track.track_axis = props.axis

    @classmethod
    def poll(cls, context):
        return context.selected_pose_bones is not None

    def execute(self, context):
        props = context.scene.loca
        props.locator_positioning = False
        for locator in locators_RT_name_list:
            self.bake_locator(context, locator)
        locators_RT_name_list.clear()
        return {'FINISHED'}

class Loca_OT_positioning_completed(Operator):
    bl_idname = 'scene.positioning_completed'
    bl_label = 'Positioning Completed'
    bl_description = 'Positioning completed'

    def execute(self, context):
        if not locators_RT_name_list:
            return {'FINISHED'}
        show_message_box(
            'Locator positioning completed, press button "Create Locators RT" to create locators', 'LOCATOR POSITIONING COMPLETED')
        return {'FINISHED'}

class Loca_PT_main_panel(Panel):
    bl_label = 'Locators'
    bl_idname = 'VIEW3D_PT_Locators'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Animation'

    def draw(self, context):
        layout = self.layout
        scena = context.scene
        props = scena.loca
        col = layout.column(align=True)
        col.label(text="Create Locators")
        col.prop(props, "baking_frame_range")
        row = col.row(align=True)
        if props.baking_frame_range:
            row.prop(props, "bake_start_fr")
            row.prop(props, "bake_end_fr")
        row = col.row(align=True)
        row.operator('scene.get_preview_range', text="Get Preview Range")
        col.prop(props, "without_baking")
        col.separator()
        col.operator('bones.locators', text='Create Locators')
        col.separator()
        col.prop(props, "select_axis")
        if props.select_axis:
            col.prop(props, "axis")
        col.separator()
        col.operator('bones.locators_rt', text='Create Locators RT')
        col.operator('scene.positioning_completed', text="Positioning Completed")

classes = [Loca_OT_get_preview_range, Loca_OT_create_locators, Loca_OT_create_locators_RT, Loca_OT_positioning_completed, Loca_PT_main_panel, locaProps]

def register():
    for cls in classes:
        register_class(cls)
    bpy.types.Scene.loca = PointerProperty(type=locaProps)

def unregister():
    for cls in classes:
        unregister_class(cls)
    del bpy.types.Scene.loca

if __name__ == '__main__':
    register()
