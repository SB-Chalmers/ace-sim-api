# Heath in Grasshopper

Two templates rebuild a Heath request with stock Honeybee and Foton
components, so students can continue a Heath study in Grasshopper:

| File | Endpoint | Models |
|---|---|---|
| `heath_split.ghx` | `POST /v1/grasshopper/split` | **The backend's two models**: a detailed daylight model of the daylight floor(s) and a simple energy model with one window per wall. Gives Heath's numbers. |
| `heath.ghx` | `POST /v1/grasshopper/detailed` | **One model for daylight and energy**: every zone has Heath's detailed windows, overhangs and fins, and the daylight floor is a zone of its own. Closer to a real building, so energy differs a little from Heath. |

The split model gives the energy simulation only what it needs: glazed area,
orientation and shading per wall. Shading every detailed window instead would
make each EnergyPlus run about 15 s slower.

## For students

1. **Install** Rhino 8, [Ladybug Tools](https://www.food4rhino.com/en/app/ladybug-tools)
   1.8 or newer, OpenStudio 3.9, and **foton** 0.3.7 from Rhino's
   `PackageManager` (set `install_` on Foton Settings to True once).
2. **Get the file.** In Heath, choose *Open in Grasshopper*. You get a `.ghx`
   with your building already filled in. (Or open a template from this folder
   and paste the Heath request JSON into the `request` panel.)
3. **Open it** in Grasshopper. The sliders show your Heath settings.
4. **Run the red groups in order:** 1 daylight factor, 2 annual daylight (sDA),
   3 energy. Each takes a few seconds.
5. **Explore.** The notes on each group say what happens there and what to try.

## What is not stock

Two small GhPython components:

1. **Heath Request** (`heath_request.py`) reads the JSON: footprint, context,
   energy zones, EPSM construction layers and the weather file.
2. **Heath Sensors** (`heath_sensors.py`) lays out the sensor grid. Heath's
   grid turns with the building, whereas *HB Sensor Grid from Rooms* follows the world axes.

Both templates also differ from the backend in two ways, neither of which changes
the results:

1. The ideal air limits are 10 MW instead of *NoLimit*, because *HB Model to OSM*
   cannot translate *NoLimit* (honeybee-openstudio 0.3.11).
2. Zone sizing is on, which OpenStudio needs for the ideal air system.

Built with the backend's own geometry, these two settings change energy by
less than 0.004 kWh/m² a year on the example request.

Not modelled in the templates yet: party walls (`shared_floors_by_edge`) and
per-edge window ratios (`wwr_by_edge`).

## For developers

1. `POST /v1/grasshopper/detailed` and `POST /v1/grasshopper/split` take a
   `/v1/simulate` body (`energy` optional) and return the filled template
   (see `api/grasshopper.py`). The request goes into the
   `request` panel, the sliders are set to its values, and the two GhPython
   components get the code in this folder.
2. To change a canvas, edit the template in Grasshopper and save it as `.ghx`.
   Keep these nicknames: `request`, the slider names in `api/grasshopper.py`,
   `all_floors_`, `Heath Request` and `Heath Sensors`.
3. `tests/test_grasshopper.py` checks that the components match the backend.
4. `POST /v1/hbjson/detailed` returns the `heath.ghx` model as an `.hbjson`
   (`build_energy_model(..., grasshopper=True)`), and `POST /v1/hbjson/energy` the
   energy model of `heath_split.ghx`, apart from the ideal air and sizing
   differences above.
