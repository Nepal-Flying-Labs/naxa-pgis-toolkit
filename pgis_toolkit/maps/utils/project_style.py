from pgis_toolkit.maps.models import LayerStyle, SubLayerStyle


def get_style_detail(layer_id,sublayer_id,project_style):
    icon,style,std_icon=None,None,None
    # icon,icon_size,style,std_icon=None,None,None,None
    layer_style_qs=LayerStyle.objects.select_related('layer','project_style')
    if sublayer_id:
        sub_layer_style_qs=SubLayerStyle.objects.select_related('sub_layer','project_style')
        if project_style=="default":
            style_instance=sub_layer_style_qs.filter(sub_layer=sublayer_id,project_style=None)
            if not style_instance.exists():
                style_instance=layer_style_qs.filter(layer=layer_id,project_style=None)
        else:
            style_instance=sub_layer_style_qs.filter(sub_layer=sublayer_id,project_style=project_style)
            if not style_instance.exists():
                style_instance=sub_layer_style_qs.filter(sub_layer=sublayer_id,project_style=None)
                if not style_instance.exists():
                    style_instance=layer_style_qs.filter(layer=layer_id,project_style=None)
    else:
        if project_style=="default":
            style_instance=layer_style_qs.filter(layer=layer_id,project_style=None)
        else:
            style_instance=layer_style_qs.filter(layer=layer_id,project_style=project_style)
            if not style_instance.exists():
                style_instance=layer_style_qs.filter(layer=layer_id,project_style=None)
    if style_instance.exists():
        # icon_url=env("URL")+style_instance[0].icon.url if style_instance[0].icon else None
        # std_icon_url=env("URL")+style_instance[0].std_icon.icon.url if style_instance[0].std_icon else None
        icon=style_instance[0].get_icon_url
        std_icon=style_instance[0].get_std_icon_url
        # icon_size=style_instance[0].icon_size
        style=style_instance[0].style
    return icon,style,std_icon
