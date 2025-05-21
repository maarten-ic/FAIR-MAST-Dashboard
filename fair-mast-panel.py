# FAIR MAST Panel Dashboard
#
# This file is licensed under the LGPL-3.0 license, available from:
# https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Copyright 2025, Ignition Computing B.V.

# Dependencies:
#   $ pip install s3fs 'zarr < 3' panel watchfiles holoviews hvplot xarray
#
# Run it with panel:
#   $ panel serve --dev --show fair-mast-panel.py

import time
from textwrap import dedent

import holoviews as hv
import hvplot.xarray  # noqa -- enable hvplot accessors for xarray Datasets
import panel as pn
import s3fs
import xarray as xr
import zarr

t0 = time.time()
hv.extension("bokeh")
pn.extension()
print(f"Loading hv/pn extensions took {time.time()-t0:.3f} seconds")

t0 = time.time()
URL = "https://mastapp.site"
# shots_df = pd.read_parquet(f"{URL}/parquet/level2/shots")
endpoint_url = "https://s3.echo.stfc.ac.uk"
url = "s3://mast/level2/shots/30421.zarr"

fs = s3fs.S3FileSystem(anon=True, endpoint_url=endpoint_url)
store = zarr.storage.FSStore(fs=fs, url=url)
zds = zarr.open(store)
groups = list(zds.group_keys())
print(f"Loading dataset groups took {time.time()-t0:.3f} seconds")


group_select = pn.widgets.MultiChoice(
    name="Select zarr groups (can be slow!):", options=groups
)

ds_cache = {}
unit_cache = {}


def data_arrays(selected_groups, current_selection):
    result = []
    for group in selected_groups:
        if group not in ds_cache:
            ds_cache[group] = xr.open_zarr(store, group=group)
            unit_cache.update(
                {
                    f"{group}/{name}": var.units
                    for name, var in ds_cache[group].data_vars.items()
                }
            )
        result.extend(f"{group}/{name}" for name in ds_cache[group].data_vars.keys())
    if current_selection:
        # Only show results with matching units
        units = unit_cache[current_selection[0]]
        result = [name for name in result if unit_cache[name] == units]
    return result


def get_arrays(array_selection):
    result = []
    for array_name in array_selection:
        group, _, name = array_name.partition("/")
        result.append(ds_cache[group][name])
    return result


def plot(array_selection, use_explorer):
    if use_explorer and len(array_selection) > 1:
        return pn.pane.Alert("Cannot plot multiple arrays when using hvplot.explorer()")
    plot = None
    if use_explorer:
        if array_selection:
            plot = get_arrays(array_selection)[0].hvplot.explorer()
    else:
        for array in get_arrays(array_selection):
            try:
                newplot = array.hvplot()
                plot = newplot if plot is None else (plot * newplot)
            except Exception as exc:
                print(exc)
    return pn.panel(plot, sizing_mode="stretch_width")


def show_details(array_selection):
    return pn.Accordion(*get_arrays(array_selection), sizing_mode="stretch_width")


def update_array_selectors(nclick):
    while len(array_selectors) < nclick:
        selector = pn.widgets.MultiChoice(name="Select arrays to plot:")
        selector.options = pn.bind(data_arrays, group_select, selector)
        array_selectors.append(selector)


def sidebar_arrayselectors(nclick):
    update_array_selectors(nclick)
    return pn.Column(*array_selectors)


def main_list(nclick):
    update_array_selectors(nclick)
    while len(main_window) // 3 < nclick:
        i = len(main_window) // 3
        array_select = array_selectors[i]
        main_window.append(pn.bind(plot, array_select, explore_checkbox))
        main_window.append(pn.bind(show_details, array_select))
        main_window.append(pn.layout.Divider())
    return pn.Column(*main_window)


array_selectors = []
add_button = pn.widgets.Button(name="+ Add plot")
main_window = []
explore_checkbox = pn.widgets.Checkbox(name="Use hvplot.explorer()")
sidebar = pn.Column(
    pn.widgets.Button(
        name="About this dashboard...",
        on_click=lambda *args: template.open_modal(),
        button_type="primary",
        sizing_mode="stretch_width",
    ),
    explore_checkbox,
    group_select,
    pn.bind(sidebar_arrayselectors, add_button.param.clicks),
    add_button,
)
main_panel = pn.bind(main_list, add_button.param.clicks)
add_button.clicks = 1
logo = "https://ignitioncomputing.com/assets/img/logo/logo.png"
template = pn.template.FastListTemplate(
    title=f"FAIR MAST Dashboard -- data @ {url}",
    sidebar=sidebar,
    main=main_panel,
    modal=pn.Column(
        dedent(
            f"""\
            # FAIR MAST Dashboard

            Prototype developed by [Ignition Computing](https://ignitioncomputing.com/)
            for viewing [public MAST data](https://mastapp.site/).

            This dashboard is available under the [LGPL-3.0 license](
            https://www.gnu.org/licenses/lgpl-3.0.en.html).

            Copyright 2025, Ignition Computing B.V.

            [![Ignition Computing Logo]({logo})](https://ignitioncomputing.com/)
            """
        ),
    ),
    main_layout=None,
)
template.servable()
