from bpy.types import Operator, Panel, PropertyGroup
from bpy.props import IntProperty, EnumProperty, BoolProperty, PointerProperty
from bpy.utils import register_class, unregister_class
import bpy
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


axes = [
    ('TRACK_X', ' X', 'Select  X', 0),
    ('TRACK_Y', ' Y', 'Select  Y', 2),
    ('TRACK_Z', ' Z', 'Select  Z', 4),
    ('TRACK_NEGATIVE_X', '-X', 'Select  -X', 1),
    ('TRACK_NEGATIVE_Y', '-Y', 'Select  -Y', 3),
    ('TRACK_NEGATIVE_Z', '-Z', 'Select  -Z', 5),
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
        name="bone axis",
        items=axes,
        description="Select local axis for rotation target",
        default="TRACK_Y",
    )

    select_axis: BoolProperty(
        name="select_axis",
        description="Select local axis for rotation target",
        default=False,
    )

    locator_positioning: BoolProperty(
        name="locator is positioning",
        description="Locator is positioning",
        default=False,
    )

    without_baking: BoolProperty(
        name="locator without baking",
        description="Locator without baking",
        default=False,
    )

    baking_frame_range: BoolProperty(
        name="baking frame range",
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

# Оператор для получения начального и конечного кадра из preview range
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

    bl_label = 'create_locators'
    bl_idname = 'bones.locators'
    bl_options = {'REGISTER', 'UNDO'}

    rt_mode: BoolProperty(
        name="rotation_target_mode",
        description="Switch to rotation target mode",
        default=False,
    )

    def create_widget(self, current_armature):
        widget_obj_name = 'wgt_loca'
        widget_created = widget_obj_name in bpy.data.objects

        # no need to add another custom control if it's already here
        if widget_created:
            return print('widget allready created')
        else:
            # switch to OBJECT mode to add empty
            bpy.ops.object.mode_set(mode='OBJECT')

            # add, name and hide empty object
            bpy.ops.object.empty_add()
            bpy.context.object.name = widget_obj_name
            bpy.context.object.hide_viewport = True

            # select armature again
            bpy.context.view_layer.objects.active = current_armature

            # switch mode back to EDIT
            bpy.ops.object.mode_set(mode='POSE')

    def create_locator(self, context, bone_P, props):
        armature = context.active_object
        st_frame = context.scene.frame_start
        end_frame = context.scene.frame_end

        print('creating locator for', bone_P.name)

        # set name for locator
        if self.rt_mode:
            locator_name = f'{bone_P.name}_LOCA_RT'
        else:
            locator_name = f'{bone_P.name}_LOCA'

        # create new bone for locator at the place of selected bone
        bpy.ops.object.mode_set(mode='EDIT')
        source_E = armature.data.edit_bones[bone_P.name]
        locator_E = armature.data.edit_bones.new(locator_name)
        locator_E.head = source_E.head
        locator_E.tail = source_E.tail
        locator_E.matrix = source_E.matrix

        bpy.ops.object.mode_set(mode='POSE')
        locator = context.object.data.bones[locator_name]
        locator_P = context.object.pose.bones[locator_name]
        # set widget for locator
        locator_P.custom_shape = bpy.data.objects["wgt_loca"]
        # make locator active in POSEMODE
        context.object.data.bones.active = locator

        # for locator add constraint from selected bone
        copy_transforms = locator_P.constraints.new('COPY_TRANSFORMS')
        copy_transforms.target = armature
        copy_transforms.subtarget = bone_P.name
        # context.object.data.bones[bone_P.name].select = False

        if self.rt_mode:
            print('locator in RT mode')
            locators_RT_name_list.append(locator_name)
            bpy.ops.pose.visual_transform_apply()
            constraint = locator_P.constraints[0]
            locator_P.constraints.remove(constraint)
            props.locator_positioning = True
            bpy.ops.pose.select_all(action='DESELECT')
            locator.select = True
            show_message_box(
                'Choose position for locator and press button "Positioning completed"', 'LOCATOR POSITIONING')

        else:
            if props.without_baking:
                bpy.ops.pose.visual_transform_apply()
                constraint = locator_P.constraints[0]
                locator_P.constraints.remove(constraint)

                child_of = locator_P.constraints.new('CHILD_OF')
                child_of.target = armature
                child_of.subtarget = bone_P.name
            else:
                print('locator in LT mode')
                print('baking locator', locator.name)

                # Switch to POSE mode if not already in it
                if bpy.context.mode != "POSE":
                    bpy.ops.object.mode_set(mode='POSE')

                # Deselect all bones
                bpy.ops.pose.select_all(action='DESELECT')

                # Select the specific bone
                armature.data.bones.active = armature.data.bones[locator_name]
                armature.pose.bones[locator_name].bone.select = True
                bpy.ops.anim.keyframe_insert_menu(type='Location')

                bpy.ops.nla.bake(frame_start=st_frame, frame_end=end_frame, only_selected=True,
                                 visual_keying=True, clear_constraints=True, use_current_action=True, bake_types={'POSE'})

                if len(locator_P.constraints) > 0:
                    print('Not baked')
                    constraint = locator_P.constraints[0]
                    locator_P.constraints.remove(constraint)
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
        return context.selected_pose_bones != None

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

    bl_label = 'create_locators_RT'
    bl_idname = 'bones.locators_rt'
    bl_options = {'REGISTER', 'UNDO'}

    def bake_locator(self, context, loc_name):
        armature = context.active_object
        props = context.scene.loca
        st_frame = context.scene.frame_start
        end_frame = context.scene.frame_end
        bone_name = loc_name.split('_LOCA')[0]
        print('locator RT', loc_name)

        locator = context.object.data.bones[loc_name]
        bone = context.object.data.bones[bone_name]
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
            if len(locator_P.constraints) > 0:
                print('Not baked')
                constraint = locator_P.constraints[0]
                locator_P.constraints.remove(constraint)
            else:
                print('locator RT baked')

            context.object.data.bones.active = bone
            hide_scale_fcurves(armature.name)
            bpy.ops.pose.select_all(action='DESELECT')
            bone.select = True
            print('bone selected')
            damped_track = pose_bone.constraints.new('DAMPED_TRACK')
            damped_track.name = 'Damped Track to locator__Loca'
            damped_track.target = armature
            damped_track.subtarget = loc_name
            damped_track.track_axis = props.axis
            print('added constraints damped track for bone')

            if bpy.context.mode != "POSE":
                bpy.ops.object.mode_set(mode='POSE')

            # Deselect all bones
            bpy.ops.pose.select_all(action='DESELECT')

            # Select the specific bone
            armature.data.bones.active = armature.data.bones[loc_name]
            armature.pose.bones[loc_name].bone.select = True

    @classmethod
    def poll(cls, context):
        return context.selected_pose_bones != None

    def execute(self, context):
        props = context.scene.loca
        props.locator_positioning = False

        for locator in locators_RT_name_list:
            self.bake_locator(context, locator)
        locators_RT_name_list.clear()

        return {'FINISHED'}


class Loca_OT_bake_and_delete(Operator):
    """Bake & delele all locators"""

    bl_label = 'bake_and_del_all_locators'
    bl_idname = 'bones.bake_and_del'
    bl_options = {'REGISTER', 'UNDO'}

    bake_on: BoolProperty(
        name="bake",
        description="Allow to bake animation for bones",
        default=True,
    )

    def bake_range_from_locator(self, context, bone_name):
        end_fr = context.scene.frame_end
        armature = context.active_object.name
        if bpy.data.objects[armature].animation_data.action:
            for fcurve in bpy.data.objects[armature].animation_data.action.fcurves:
                if f'{bone_name}_LOCA' in fcurve.data_path.split('"')[1]:
                    end_fr = int(fcurve.keyframe_points[-1].co[0])
        return end_fr

    def bake(self, context, bone_name):
        print('baking bone', bone_name)
        armature = context.active_object
        st_frame = context.scene.frame_start
        end_frame = context.scene.frame_end
        for bone in context.object.pose.bones:
            if bone.name == bone_name:
                bone_P = context.object.pose.bones[bone_name]

                bpy.ops.pose.select_all(action='DESELECT')
                bone = context.object.data.bones[bone_name]
                bone.select = True
                print('bone selected')
                end_frame = self.bake_range_from_locator(context, bone_name)
                if self.bake_on:
                    bpy.ops.nla.bake(frame_start=st_frame, frame_end=end_frame, only_selected=True,
                                     visual_keying=True, clear_constraints=False, use_current_action=True, bake_types={'POSE'})
                    print('bone baked')
                for constraint in bone_P.constraints:
                    if '__Loca' in constraint.name:
                        bone_P.constraints.remove(constraint)
                print('deleting remaining constraints')
                hide_scale_fcurves(armature.name, bone_name)

    def deleteLocators(self, context, loc_name):
        armature = context.active_object
        print('deleting', loc_name)
        for bone in armature.data.edit_bones:
            if bone.name == loc_name:
                armature.data.edit_bones.remove(bone)

    def deleteUselessFCurves(self, context):
        armature = context.active_object
        if bpy.data.objects[armature.name].animation_data.action:
            anim_fcurves = bpy.data.objects[armature.name].animation_data.action.fcurves
            for fcurve in anim_fcurves:
                if '_LOCA' in fcurve.data_path:
                    anim_fcurves.remove(fcurve)

#    @classmethod
#    def poll(cls, context):
#        return True

    def execute(self, context):
        props = context.scene.loca
        armature = context.active_object

        bones_name_list = set()
        for bone in armature.pose.bones:
            if '_LOCA' in bone.name:
                bones_name_list.add(bone.name.split('_LOCA')[0])

        for bone in bones_name_list:
            self.bake(context, bone)

        bpy.ops.object.mode_set(mode='EDIT')

        locators_name_list = []
        for bone in armature.pose.bones:
            if '_LOCA' in bone.name:
                locators_name_list.append(bone.name)

        print('deleting locators', locators_name_list)
        for loc in locators_name_list:
            self.deleteLocators(context, loc)
        bpy.ops.object.mode_set(mode='POSE')

        for bone in armature.data.bones:
            if '_LOCA' in bone.name:
                print('bone with "_LOCA"', bone.name)
                self.deleteLocators(context, bone.name)

        self.deleteUselessFCurves(context)

        widget_ob = bpy.data.objects['wgt_loca']
        bpy.data.objects.remove(widget_ob)

        bones_name_list.clear()
        locators_name_list.clear()
        locators_RT_name_list.clear()

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
                    col1.operator(Loca_OT_bake_and_delete.bl_idname,
                                  text="bake bones & delete locators").bake_on = True
                    col1.operator(Loca_OT_bake_and_delete.bl_idname,
                                  text="delete locators").bake_on = False
            else:
                col.prop(props, "select_axis", text='select local axis')
                if props.select_axis:
                    row = col.row(align=True)
                    row.prop(props, "axis", expand=True)
                col.operator(Loca_OT_create_locators_RT.bl_idname,
                             text="positioning completed")
                
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
    Loca_OT_bake_and_delete,
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
