# Boond: every drop, on time

Boond Live is a daily irrigation and heat-alert service for small farms. Each morning it decides one action for a registered field (**IRRIGATE**, **SKIP**, **WAIT** or **HEAT PROTECTION**) with an amount in millimetres, and explains it in a short Hindi or English message. AWS hackathon, Track 02: Heat and Water.

The decision comes from a standard crop-water model (FAO-56). The language model only rewrites the engine's message, and every number it writes is checked against the engine output.

> **Status:** the decision engine is complete and tested (this repository). The AWS pipeline (daily job, storage, Web Push, Hindi audio) and the web app are the next stage.

## What is real and what is modelled

| Real | Modelled |
|---|---|
| Weather: Open-Meteo forecast and ERA5 archive | Field soil-water balance (FAO-56; no free live soil-moisture data exists for one farm) |
| Farmer check-ins that correct the balance | Savings against a published baseline schedule, always labelled as estimates |
| The 2021-22 Ludhiana season used for validation | Pump energy from the farmer's lift and pump efficiency |

## Quick start

```bash
pip install -r requirements-dev.txt
python -m pytest -q                       # 268 tests, includes FAO-56 Example 37
python -m engine.check_data               # data files are consistent
python replay/replay.py --weather replay/cache/ludhiana_actual_2021_22.json \
       --crop wheat --sow 2021-11-05 --soil loam      # offline 2021-22 replay
```

The replay runs offline from the cached weather in `replay/cache/`. `--crop wheat` picks the timely, late or January wheat profile from the sowing date, as field registration does (`--crop sugarcane` likewise picks spring or autumn cane).

## How the engine decides

Every morning, for each field (`engine/field_runner.advance_field`):

1. **Catch up to yesterday.** Each unprocessed day is applied with observed weather and the farmer's check-ins:
   - crop coefficient Kc by growth stage (FAO-56 Eq. 66);
   - growing root depth and the soil's water capacity (TAW);
   - readily available water RAW = p × TAW, with p adjusted for crop water demand;
   - water-stress factor Ks;
   - rain counts only if it is at least 0.2 × ET0;
   - depletion is kept between 0 and TAW.
2. **Decide today**, in this order:
   0. Nothing after the crop's last irrigation date (PAU wheat 31 March or 10 April, cotton 30 September, sugarcane 30 days before harvest, paddy day 95): WAIT, "stop irrigating".
   1. HEAT PROTECTION if the crop is in a heat-sensitive stage and a hot day is forecast within 3 days (cotton and sugarcane: 2 hot days in a row).
   2. IRRIGATE if the field is past RAW, will reach it within 2 days, or a critical growth-stage irrigation is due (wheat crown-root initiation).
   3. SKIP only if confident forecast rain keeps the field below RAW. Uncertain or missing rain probability is never trusted.
   4. Otherwise WAIT, with the expected day of the next irrigation.
3. **Report.** Litres, kWh, CO2e and cost, a 16-day outlook of projected depletion, and the message text (`engine/messages.py`). Every message ends with "this is advice, the final decision is yours". If the sowing date was outside the crop's recommended window, a warning is added; the advice itself does not change.

The replay and the live job use the same functions. A test runs the whole 2021-22 season through the live path and checks that it matches the replay day by day (`engine/tests/test_field_runner.py`). See `docs/ENGINE.md` for the backend interface.

## Validation: 2021-22 replay at Ludhiana (simulation)

These runs use observed weather (Open-Meteo ERA5 archive) as a stand-in for the forecast, with forecast rain not trusted. The baselines are published schedules (`engine/baseline.json`):

| Crop (loam) | Boond | Baseline |
|---|---|---|
| Wheat, sown 5 Nov 2021 | 3 irrigations, 162 mm, **0 stress days** | PAU: 2 irrigations, 125 mm, 14 stress days |
| Late wheat, sown 1 Dec 2021 | 4 irrigations, 225 mm, 0 stress days | PAU: 2 irrigations, 125 mm, 31 stress days (12 after 31 March) |
| January wheat, sown 5 Jan 2022 | 5 irrigations, 241 mm, 0 stress days before 10 April (9 after) | PAU: 3 irrigations, 200 mm, 34 stress days (18 after 10 April) |
| Cotton, sown 1 May 2021 | 6 irrigations, 282 mm, 0 stress days | CICR/PAU interval: 6 irrigations, 450 mm, 8 stress days |
| Sugarcane, planted 1 Mar 2021 | 12 irrigations, 750 mm, 0 stress days | PAU/TNAU interval: 20 irrigations, 1500 mm, 8 stress days |
| Paddy, transplanted 25 Jun 2021 | 7 irrigations, 528 mm, 7 stress days (all after the day-95 stop) | PAU rule: 7 irrigations, 525 mm, 8 stress days (all after the stop) |

Stress days after the last irrigation date are the intended drying-off before harvest, so they are counted separately (`drying_off_stress_days`) in both runs.

For wheat, Boond advised:
- the crown-root irrigation on 2 Dec 2021, after a dry November;
- nothing during the wet January;
- an irrigation on 28 Feb;
- a heat-protection irrigation in the March 2022 heatwave (17 Mar).

For late wheat, the April 2022 heat no longer triggers an irrigation on 4 April, because PAU allows irrigation of wheat sown by 5 December only up to 31 March. January wheat needed no crown-root irrigation, because 119 mm of rain fell in January 2022.

Boond's wheat schedule uses **more** water than the PAU calendar but avoids its stress days, so it is presented as stress avoidance, not water saving. The cotton and sugarcane baselines use interval assumptions (marked in `engine/baseline.json`), so their savings are estimates. Paddy follows the PAU rule in both runs. These figures are pinned in `engine/tests/test_replay_2021_22.py`.

## Data sources and licences

- **Weather:** [Open-Meteo](https://open-meteo.com/) forecast and archive APIs, data under **CC BY 4.0**. The cached season is in `replay/cache/`; `tools/fetch_weather.py` downloads it again.
- **Crop water method:** Allen et al. (1998), *FAO Irrigation and Drainage Paper 56*, Tables 11, 12, 17, 19 and 22, Eq. 62, 66 and Example 37.
- **Punjab practice:** Punjab Agricultural University, *Package of Practices* Rabi 2025-26 and Kharif 2026; PAU Ludhiana field studies (Kaur et al. 2017, 2025); CICR cotton package for Punjab; TNAU Agritech (sugarcane, rice); AICRP on Sugarcane / ICAR-IISR 2017 (planting seasons); Abazied & El-Laboudy 2021 (sugarcane drying-off).
- **Heat thresholds:** Porter & Gawith 1999 (wheat); Jagadish et al. 2007 (rice); Oosterhuis & Snider 2011 (cotton); SASRI 2025 (sugarcane).
- **Emissions:** CEA CO2 Baseline Database v22.0, FY 2025-26: 0.675 kg CO2 per kWh.

Every value, its source and whether it is an assumption are listed in `docs/DATA_GUIDE.md`. Section 5 of that file is the assumptions register.

## Key assumptions (editable in `engine/config.json`)

- **Root zone at sowing:** assumed full, after the PAU pre-sowing irrigation.
- **Check-ins:**
  - "I watered" light / normal / heavy = 50 / 75 / 100 mm. PAU irrigates 7.5 cm per irrigation and 10 cm before sowing.
  - "It rained" little / moderate / heavy = 8 / 30 / 65 mm, set at or below the IMD rainfall bands.
- **Forecast rain** counts only at 70% probability or more.
- **Heat-protection irrigation** is 40 mm, the smallest depth that can be spread by flood irrigation. The maximum advised depth is 75 mm (PAU's 7.5 cm).
- **Energy:** pump efficiency 0.40 by default, and field application efficiency 0.70, so litres and kWh are worked out on the pumped amount.
- **Tariff:** Rs 8/kWh, shown as the cost to the power system. Farm power in Punjab is free to the farmer.

## Limitations

- Advice comes from a modelled soil-water balance, corrected only by farmer check-ins; no soil moisture is measured.
- The FAO-56 crop-coefficient climate adjustment is not implemented.
- Paddy, cotton and sugarcane stage lengths and heat windows are partly derived (see `docs/DATA_GUIDE.md`). So are the January-wheat and autumn-sugarcane profiles; autumn sugarcane (420 days) is longer than the cached weather and has not been replayed.
- In the replay, observed weather stands in for the forecast. No archived rain probabilities were available, so forecast rain was not trusted.

## Repository layout

```
engine/          decision engine (pure Python, no network)
  field_runner.py  daily path shared by the live job and the replay
  water_balance.py, kc.py, advisor.py, heat_rules.py, critical.py, paddy.py
  season_rules.py  sowing windows and the last irrigation before harvest
  messages.py      Hindi / English text; number check for Bedrock rewrites
  replay.py, simulate.py, baseline.json   validation replay
  crops.json, soils.json, config.json, messages.json   sourced parameters
  tests/           268 tests
replay/          replay.py (spec command) and cache/ (2021-22 weather)
tools/           fetch_weather.py (Open-Meteo download)
docs/            DATA_GUIDE.md (sources, assumptions), ENGINE.md (backend interface)
```

## AI tools used

_Fill in before submission: list each AI coding or writing tool the team used and what for (spec 18.1)._
