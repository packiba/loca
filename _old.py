import bpy
from bpy.types import Operator, Panel, PropertyGroup
from bpy.props import IntProperty, EnumProperty, BoolProperty, PointerProperty
from bpy.utils import register_class, unregister_class

bl_info = {
    "name": "loca",
    "author": "Pavel Kiba",
    "version": (1, 1, 0),
    "blender": (4, 1, 0),
    "location": "View3D > N-Panel > Animation",
    "description": "Create bone locators for animation",
    "warning": "",
    "doc_url": "",
    "category": "Animation", }

# Define axes for rotation target
axes = [
    ('TRACK_X', ' X', 'Select  X', 0),
    ('TRACK_Y', ' Y', 'Select  Y', 2),
    ('TRACK_Z', ' Z', 'Select  Z', 4),
    ('TRACK_NEGATIVE_X', '-X', 'Select  -X', 1),
    ('TRACK_NEGATIVE_Y', '-Y', 'Select  -Y', 3),
    ('TRACK_NEGATIVE_Z', '-Z', 'Select  -Z', 5),
]

# Global list to store locator names for rotation target
global locators_RT_name_list
locators_RT_name_list = []

# Function to show a message box
def show_message_box(message="", ttl="Message Box", ic='INFO'):
    def draw(self, context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title=ttl, icon=ic)

# Function to hide scale F-curves
def hide_scale_fcurves(armature_name, bone_name='_LOCA'):
    if bpy.data.objects[armature_name].animation_data.action:
        for fcurve in bpy.data.objects[armature_name].animation_data.action.fcurves:
            if '_LOCA' in fcurve.data_path or bone_name in fcurve.data_path:
                if 'scale' in fcurve.data_path:
                    fcurve.hide = True

# Property group to store addon properties
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
        default = 1,
    )

    bake_end_fr: IntProperty(
        name="End",
        description="Baking end frame",
        default = 1,
    )

# Operator to get the preview range
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

# Operator to create locators
class Loca_OT_create_locators(Operator):
    """Create locators"""

    bl_label = 'create_locators'
    bl_idname = 'bones.locators'
    bl_options = {'REGISTER', 'UNDO'}

    rt_mode: BoolProperty(
        name="rotation_target_mode",
        description="Switch to rotation target mode",
        default=False,
    )

    # Function to create a widget for locators
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

    # Function to create a locator bone
    def create_locator(self, context, bone_P, props):
        armature = context.active_object
        st_frame = props.bake_start_fr
        end_frame = props.bake_end_fr

        # Set start and end frames to scene frame range if baking_frame_range is False
        if not props.baking_frame_range:
            st_frame = context.scene.frame_start
            end_frame = context.scene.frame_end

        # Generate unique locator name
        locator_base_name = f'{bone_P.name}_LOCA_RT' if self.rt_mode else f'{bone_P.name}_LOCA'
        locator_name = locator_base_name
        count = 1
        while locator_name in armature.pose.bones:
            locator_name = f"{locator_base_name}.{count:03d}"
            count += 1

        # # set name for locator
        # if self.rt_mode:
        #     locator_name = f'{bone_P.name}_LOCA_RT'
        # else:
        #     locator_name = f'{bone_P.name}_LOCA'

        # create new bone for locator at the place of selected bone
        bpy.ops.object.mode_set(mode='EDIT')
        source_E = armature.data.edit_bones[bone_P.name]
        locator_E = armature.data.edit_bones.new(locator_name)
        locator_E.head = source_E.head
        locator_E.tail = source_E.tail
        locator_E.matrix = source_E.matrix

        bpy.ops.object.mode_set(mode='POSE')
        locator_P = context.object.pose.bones[locator_name]
        # set widget for locator
        locator_P.custom_shape = bpy.data.objects["wgt_loca"]
        # make locator active in POSEMODE
        context.object.data.bones.active = locator_P.bone

        # for locator add constraint from selected bone
        copy_transforms = locator_P.constraints.new('COPY_TRANSFORMS')
        copy_transforms.target = armature
        copy_transforms.subtarget = bone_P.name

        if self.rt_mode:
            print('locator in RT mode')
            locators_RT_name_list.append(locator_name)
            bpy.ops.pose.visual_transform_apply()
            constraint = locator_P.constraints[0]
            locator_P.constraints.remove(constraint)
            props.locator_positioning = True
            bpy.ops.pose.select_all(action='DESELECT')
            locator_P.bone.select = True
            show_message_box(
                'Choose position for locator and press button "Apply locator placement"', 'LOCATOR POSITIONING')

        else:
            if props.without_baking:
                bpy.ops.pose.visual_transform_apply()
                constraint = locator_P.constraints[0]
                locator_P.constraints.remove(constraint)

                # child_of = locator_P.constraints.new('CHILD_OF')
                # child_of.target = armature
                # child_of.subtarget = bone_P.name
            else:
                bpy.ops.pose.select_all(action='DESELECT')

                # Select the specific bone
                locator_P.bone.select = True
                bpy.ops.anim.keyframe_insert_menu(type='Location')

                bpy.ops.nla.bake(frame_start=st_frame, frame_end=end_frame, only_selected=True,
                                 visual_keying=True, clear_constraints=True, use_current_action=True, bake_types={'POSE'})

                if locator_P.constraints:
                    print('Not baked')
                    locator_P.constraints.remove(locator_P.constraints[0])
                else:
                    hide_scale_fcurves(armature.name)
                    copy_transforms = bone_P.constraints.new('COPY_TRANSFORMS')
                    copy_transforms.name = 'Copy locator transforms__Loca'
                    copy_transforms.target = armature
                    copy_transforms.subtarget = locator_name
                    print(f'{bone_P.name} received location from locator')

                    if bpy.context.mode != "POSE":
                        bpy.ops.object.mode_set(mode='POSE')

                    # Deselect all bones
                    bpy.ops.pose.select_all(action='DESELECT')

                    # Select the specific bone
                    armature.data.bones.active = armature.data.bones[locator_name]
                    armature.pose.bones[locator_name].bone.select = True

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

# Operator to create locators for rotation target
class Loca_OT_create_locators_RT(Operator):
    """Create locators for rotation target"""

    bl_label = 'create_locators_RT'
    bl_idname = 'bones.locators_rt'
    bl_options = {'REGISTER', 'UNDO'}

    # Function to bake locator
    def bake_locator(self, context, loc_name):
        armature = context.active_object
        props = context.scene.loca
        st_frame = props.bake_start_fr
        end_frame = props.bake_end_fr

        # Set start and end frames to scene frame range if baking_frame_range is False
        if not props.baking_frame_range:
            st_frame = context.scene.frame_start
            end_frame = context.scene.frame_end

        bone_name = loc_name.split('_LOCA')[0]
        print('locator RT', loc_name)

        locator = context.object.data.bones[loc_name]
        locator_P = context.object.pose.bones[loc_name]
        context.object.data.bones.active = locator
        pose_bone = context.object.pose.bones[bone_name]

        child_of = locator_P.constraints.new('CHILD_OF')
        child_of.target = armature
        child_of.subtarget = bone_name
        print('constraints added')

        if props.without_baking:
            bpy.ops.pose.visual_transform_apply()
            constraint = locator_P.constraints[0]
            locator_P.constraints.remove(constraint)
            child_of = locator_P.constraints.new('CHILD_OF')
            child_of.target = armature
            child_of.subtarget = bone_name
            print('added constraints child of for locator')
        else:
            # Switch to POSE mode if not already in it
            if bpy.context.mode != "POSE":
                bpy.ops.object.mode_set(mode='POSE')

            # Deselect all bones
            bpy.ops.pose.select_all(action='DESELECT')

            # Select the specific bone
            armature.data.bones.active = armature.data.bones[loc_name]
            armature.pose.bones[loc_name].bone.select = True
            bpy.ops.anim.keyframe_insert_menu(type='Location')

            bpy.ops.nla.bake(frame_start=st_frame, frame_end=end_frame, only_selected=True,
                             visual_keying=True, clear_constraints=True, use_current_action=True, bake_types={'POSE'})
            locator_P = context.object.pose.bones[locator.name]
            if locator_P.constraints:
                locator_P.constraints.remove(locator_P.constraints[0])
            hide_scale_fcurves(armature.name)
            damped_track = pose_bone.constraints.new('DAMPED_TRACK')
            damped_track.name = 'Damped Track to locator__Loca'
            damped_track.target = armature
            damped_track.subtarget = loc_name
            damped_track.track_axis = props.axis

            if bpy.context.mode != "POSE":
                bpy.ops.object.mode_set(mode='POSE')

            # Deselect all bones
            bpy.ops.pose.select_all(action='DESELECT')

            # Select the specific bone
            armature.data.bones.active = armature.data.bones[loc_name]
            armature.pose.bones[loc_name].bone.select = True

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


class Loca_OT_bake_locators(Operator):
    """Bake bones without deleting locators"""

    bl_label = 'bake_locators'
    bl_idname = 'bones.bake_locators'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armature = context.active_object
        props = context.scene.loca
        st_frame = props.bake_start_fr
        end_frame = props.bake_end_fr

        # Set start and end frames to scene frame range if baking_frame_range is False
        if not props.baking_frame_range:
            st_frame = context.scene.frame_start
            end_frame = context.scene.frame_end

        locators = []
        for bone in armature.pose.bones:
            if 'LOCA' in bone.name:
                locators.append(bone.name)

        bpy.ops.object.mode_set(mode='POSE')
        for loc in locators:
            bpy.context.object.data.bones.active = bpy.context.object.data.bones[loc]
            bpy.ops.nla.bake(
                frame_start=st_frame, frame_end=end_frame,
                only_selected=False, visual_keying=True,
                clear_constraints=True, use_current_action=True,
                bake_types={'POSE'}
            )

        return {'FINISHED'}
    
class Loca_OT_bake_selected_locators(Operator):
    """Bake selected locators"""

    bl_label = 'bake_selected_locators'
    bl_idname = 'bones.bake_selected_locators'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armature = context.active_object
        props = context.scene.loca
        st_frame = props.bake_start_fr
        end_frame = props.bake_end_fr

        # Set start and end frames to scene frame range if baking_frame_range is False
        if not props.baking_frame_range:
            st_frame = context.scene.frame_start
            end_frame = context.scene.frame_end

        selected_locators = [bone.name for bone in context.selected_pose_bones if 'LOCA' in bone.name]

        bpy.ops.object.mode_set(mode='POSE')
        for loc in selected_locators:
            bpy.context.object.data.bones.active = bpy.context.object.data.bones[loc]
            bpy.ops.nla.bake(
                frame_start=st_frame, frame_end=end_frame,
                only_selected=False, visual_keying=True,
                clear_constraints=True, use_current_action=True,
                bake_types={'POSE'}
            )

        return {'FINISHED'}
    
class Loca_OT_delete_all_locators(Operator):
    """Delete all locators"""

    bl_label = 'delete_all_locators'
    bl_idname = 'bones.delete_all_locators'
    bl_options = {'REGISTER', 'UNDO'}

    bake_on: BoolProperty(
        name="bake",
        description="Bake bones with locators",
        default=True,
    )

    def execute(self, context):
        armature = context.active_object

        bpy.ops.object.mode_set(mode='EDIT')
        for bone in armature.data.edit_bones:
            if 'LOCA' in bone.name:
                armature.data.edit_bones.remove(bone)

        bpy.ops.object.mode_set(mode='POSE')

        return {'FINISHED'}

    
class Loca_OT_delete_selected_locators(Operator):
    """Delete selected locators"""

    bl_label = 'delete_selected_locators'
    bl_idname = 'bones.delete_selected_locators'
    bl_options = {'REGISTER', 'UNDO'}

    bake_on: BoolProperty(
        name="bake",
        description="Bake bones with locators",
        default=True,
    )

    def delete_locators(self, context, loc_name):
        armature = context.active_object
        for bone in armature.data.edit_bones:
            if bone.name == loc_name:
                armature.data.edit_bones.remove(bone)

    def execute(self, context):
        armature = context.active_object
        selected_bones = context.selected_pose_bones
        locators_to_delete = []

        for bone in selected_bones:
            if '_LOCA' in bone.name:
                locators_to_delete.append(bone.name)

        bpy.ops.object.mode_set(mode='EDIT')
        for loc in locators_to_delete:
            self.delete_locators(context, loc)
        bpy.ops.object.mode_set(mode='POSE')

        return {'FINISHED'}



class OBJECT_PT_loca(Panel):
    bl_label = f"Loca {bl_info['version'][0]}.{bl_info['version'][1]}.{bl_info['version'][2]}"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = f"Loca {bl_info['version'][0]}.{bl_info['version'][1]}.{bl_info['version'][2]}"

    def draw(self, context):

        props = context.scene.loca
        is_any_locator = False
        for bone in context.object.pose.bones:
            if 'LOCA' in bone.name:
                is_any_locator = True

        if context.object.mode == 'POSE':
            layout = self.layout
            col = layout.column()
            if not props.locator_positioning:
                col.prop(props, "without_baking", text='without baking')
                col1 = col.column(align=True)
                col1.operator(Loca_OT_create_locators.bl_idname,
                              text="location target").rt_mode = False
                col1.operator(Loca_OT_create_locators.bl_idname,
                              text="rotation target").rt_mode = True
                if is_any_locator:
                    col.separator()
                    col1 = col.column(align=True)
                    row1 = col1.row(align=True)
                    row1.operator(Loca_OT_bake_locators.bl_idname,text="bake all").bake_on = True
                    row1.operator(Loca_OT_bake_selected_locators.bl_idname, text="bake selected")
                    row2 = col1.row(align=True)
                    row2.operator(Loca_OT_delete_all_locators.bl_idname,
                                  text="delete all").bake_on = True
                    row2.operator(Loca_OT_delete_selected_locators.bl_idname, text="delete selected")
            else:
                col.prop(props, "select_axis", text='select local axis')
                if props.select_axis:
                    row = col.row(align=True)
                    row.prop(props, "axis", expand=True)
                col.operator(Loca_OT_create_locators_RT.bl_idname,
                             text="Apply locator placement", depress=True)
                
            col1 = col.column(align=True)
            if props.baking_frame_range:
                box = col1.box()
                row = box.row(align=True)
                row.prop(props, "baking_frame_range", text='Bake in frame range')
                row.operator(Loca_OT_get_preview_range.bl_idname, text="Preview Range")
            else:
                col2 = col1.column()
                col2.prop(props, "baking_frame_range", text='Bake in frame range')
            if props.baking_frame_range:
                row = box.row(align=True)
                row.prop(props, "bake_start_fr")
                row.prop(props, "bake_end_fr")



classes = [
    locaProps,
    Loca_OT_get_preview_range,
    Loca_OT_create_locators,
    Loca_OT_create_locators_RT,
    Loca_OT_delete_all_locators,
    Loca_OT_delete_selected_locators,
    OBJECT_PT_loca,
]


def register():
    for cl in classes:
        register_class(cl)

    bpy.types.Scene.loca = PointerProperty(type=locaProps)


def unregister():
    for cl in reversed(classes):
        unregister_class(cl)


if __name__ == "__main__":
    register()
