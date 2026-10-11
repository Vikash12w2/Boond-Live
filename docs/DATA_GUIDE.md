# Boond: crop, soil and energy data guide

Data pack for wheat, paddy, cotton and sugarcane. Version 2026-10-08.

## 1. What this data is (and isn't)

Boond's engine is the FAO-56 water balance (spec section 6). It is deterministic and uses no ML, so **nothing is trained**. These files supply the engine's **parameters**: crop coefficients, stage lengths, root depths, soil water limits, heat thresholds and irrigation depths. Each value is either taken from a published source or marked `ASSUMPTION` with the reasoning.

Real field data is still used in two places:

- **Validation:** the 2021-22 replay, compared with a baseline schedule from PAU's published recommendations (`engine/baseline.json`).
- **Correction:** farmer check-ins (`I watered`, `It rained`) adjust the water balance as the season runs.

If you later add a learned component (beyond this hackathon), the targets in `validation_targets` and the `kc_local_measured` blocks are the place to start calibrating.

## 2. Files

| File | Replaces | What's new |
|---|---|---|
| `engine/crops.json` | your crops.json | 10 crop profiles (including very late wheat and autumn sugarcane), sowing windows and last-irrigation rules for every crop, Punjab stage lengths, heat windows with day ranges, root-growth day, per-crop irrigation depths, paddy pond rules, seasonal sanity targets |
| `engine/soils.json` | your soils.json | Same 3 farmer soils with unchanged values, plus REW/TEW, paddy percolation, Hindi labels, 5 extra texture classes, a SoilGrids suggestion rule |
| `engine/config.json` | your config.json | Same keys, cited or justified values, plus check-in rain values, CEA 2025-26 emission factor, Kc climate adjustment switch |
| `engine/baseline.json` | new | PAU/CICR/TNAU calendar schedules for all 4 crops, including PAU's rain-delay rule for wheat |
| `engine/check_data.py` | new | Checks structure (`python -m engine.check_data`), prints Kc and TAW/RAW tables with `--tables`, and computes seasonal ETc from a cached weather file with `--weather` |

All existing keys keep their shape: `total_days`, `stages.*.days/kc_start/kc_end`, `heat_thresholds`, `depletion_fraction` and `root_depth.initial_m/maximum_m`. Existing `kc.py` and `water_balance.py` code keeps working. **Ignore every key that starts with `_`**: these hold documentation. Don't list them as crops in the form.

## 3. The most important change: wheat is ~145 days in Punjab, not 120

PAU's recommended timely-sown varieties mature in 145-158 days: PBW 826 in 148, HD 3086 in 148, DBW 187 in 153, Unnat PBW 343 in 155 and PBW 869 in 158. The 15/25/50/30 = 120-day row in FAO-56 Table 11 is for **Central India**. PAU Ludhiana measured the stage lengths below (Kaur et al. 2017):

| Sowing | Initial | Development | Mid | Late | Total |
|---|---|---|---|---|---|
| 28 Oct | 25 | 41 | 51 | 29 | 146 |
| 4 Nov | 23 | 46 | 43 | 32 | 144 |
| 25 Nov | 25 | 45 | 35 | 28 | 133 |
| 2 Dec | 29 | 40 | 30 | 27 | 126 |

- `wheat` uses the mean of the first two rows: 24/44/47/30 = 145.
- `wheat_late` uses the 25 Nov row.
- `wheat_fao56` is the original 120-day profile, kept for unit tests and central-India fields.

The heat windows are also day-based now. At PAU, wheat headed at 96-99 days after sowing (DAS) and reached physiological maturity at 146-154 DAS (Kaur et al. 2025). That puts flowering at about 92-110 DAS and grain filling at about 106-140 DAS. With the 120-day profile, a window of "days 80-100" would have fallen in the wrong weeks.

## 4. How the engine should use the data

### 4.1 Pick the profile when a field is registered

Use `engine.data.select_profile(crop, sowing_date, variety=None, ratoon=False)`:

| Crop | Date given | Profile | Source of the split |
|---|---|---|---|
| Wheat | up to 21 Nov | `wheat` | PAU timely window ends 21 Nov (Rabi 2025-26, p.17) |
| Wheat | 22 Nov – 31 Dec | `wheat_late` | PAU late window 22 Nov – 20 Dec; later December sowings get a warning |
| Wheat | 1 Jan – 30 Jun | `wheat_january` | PAU recommends PBW 757 (about 114 days) for January sowing |
| Paddy | transplanting | `paddy`, `paddy_short` for PR 126 | |
| Sugarcane | Jan – Jul | `sugarcane` (spring) | AICRP / ICAR-IISR 2017: North-West zone plants spring cane in Feb–Mar |
| Sugarcane | Aug – Dec | `sugarcane_autumn` | Same bulletin: autumn cane in Sep–Oct |
| Sugarcane | ratoon | `sugarcane_ratoon` | |
| Cotton | sowing | `cotton` | |

Store the profile key on the PROFILE item so later edits to crops.json don't silently change running fields.

**Sowing window.** Every profile except `wheat_fao56` and `sugarcane_ratoon` has a recommended window (`sowing_window`, `transplant_window` or `planting_window`, as MM-DD). `engine.season_rules.check_sowing_window` compares the farmer's date with it. Outside the window, the advice carries a `SOWN_AFTER_WINDOW` or `SOWN_BEFORE_WINDOW` warning with the number of days. The warning tells the farmer that yield may be lower; it does not change the irrigation advice, because the crop's water need is the same.

**Last irrigation before harvest.** Irrigating a ripening crop wastes water and can harm it, so each profile says when Boond stops advising irrigation (`engine.season_rules.last_irrigation`):

| Profile | Last irrigation | Source |
|---|---|---|
| `wheat`, `wheat_late` | 31 March; 10 April if sown after 5 December | PAU Rabi 2025-26 p.17 |
| `wheat_january` | 10 April | PAU Rabi 2025-26 p.17 |
| `cotton` | 30 September | CICR/PAU Package of Practices for Cotton, Punjab: "to hasten boll opening" |
| `sugarcane`, `sugarcane_autumn`, `sugarcane_ratoon` | 30 days before harvest | Abazied & El-Laboudy 2021 (30 days gave the best sugar recovery); FAO: irrigation is stopped to ripen the cane. ASSUMPTION for Punjab |
| `paddy`, `paddy_short` | `paddy_water.stop_irrigation_day` | PAU Kharif 2026 p.12 |

After that day the advice is WAIT with `IRRIGATION_STOPPED`, even in a heat wave. The replay counts stress days after the last irrigation date separately (`drying_off_stress_days`), in both runs, because they are intended.

**Date label in the form:** for wheat and cotton, ask for the sowing date. For paddy, ask for the transplanting date (day 1 is transplanting, and the nursery is not modelled). For sugarcane, ask for the planting date, or the last harvest date for a ratoon crop.

### 4.2 Daily calculation (upland crops: wheat, cotton, sugarcane)

```text
day      = (date - sowing_date).days + 1
Kc       = constant in initial and mid; linear in development and late      (crops.json _meta)
Zr       = initial_m -> maximum_m, linear until root_depth.full_depth_day
TAW      = 1000 x (theta_fc - theta_wp) x Zr                                (soils.json)
p        = depletion_fraction (+ depletion_fraction_by_stage if you support it)
p_adj    = clamp(p + 0.04 x (5 - ETc), 0.1, 0.8)                            (FAO-56 Table 22 note)
RAW      = p_adj x TAW
P_eff    = rain if rain >= 0.2 x ET0 else 0                                 (config.rain)
Ks       = 1 if D <= RAW else (TAW - D) / ((1 - p_adj) x TAW)
D_today  = clamp(D_yesterday - P_eff - I + Ks x Kc x ET0, 0, TAW)
```

As roots grow, TAW grows too. Keep D in mm and don't rescale it. The new soil the roots reach is assumed to be at field capacity, which is the standard FAO-56 simplification.

**Kc check:** `engine/tests/test_kc.py` asserts the FAO-56 Eq. 66 values for every crop profile.

### 4.3 Heat rule, generalised to any crop

Replace the hard-coded wheat windows with a loop over `heat_windows`:

```python
for w in crop["heat_windows"]:
    if w["day_start"] <= day_of_forecast <= w["day_end"] and tmax >= w["tmax_threshold_c"]:
        raise_heat_warning(w["name"])
```

Check each forecast day within `config.heat.forecast_window_days`, using that forecast day's crop day, not today's. In May-June, cotton (35 °C) and sugarcane (40 °C) cross their thresholds almost daily in Punjab, so these profiles set `heat_consecutive_days: 2`: HEAT PROTECTION needs two hot days in a row within the 3-day window, the same persistence IMD requires before declaring a heat wave. Other crops use `config.heat.consecutive_days_required` (1). In the 2021-22 replay this cut the heat-reason days from 27 to 20 for cotton and from 19 to 10 for sugarcane.

### 4.4 Irrigation depth

- **IRRIGATE:** advise net depth ≈ D. Cap it at `crop.irrigation.max_advised_depth_mm` (75 mm, PAU's 7.5 cm), or at `config.irrigation.maximum_depth_mm` if the crop doesn't set a cap. Round up to `minimum_advised_depth_mm` (40 mm).
- **HEAT PROTECTION:** `config.irrigation.light_depth_mm` (40 mm).
- **Cotton and sugarcane RAW can exceed 75 mm.** On loam, cotton's RAW is 84 mm and sugarcane's is 101 mm. A 75 mm cap then leaves the soil partly depleted, so the next IRRIGATE comes sooner. This is intended: it matches how farmers flood-irrigate. Raise the cap to 100 mm for sugarcane if you prefer fewer, larger irrigations.
- **Litres and kWh:** spec 6.7 uses net depth. If you set `config.irrigation.application_efficiency` (0.70), divide by it to get the volume actually pumped, and say which you used.

### 4.5 Check-ins

```text
WATERED level -> crops[profile].irrigation.checkin_depth_mm[level]       (50 / 75 / 100 mm)
RAIN    level -> config.checkin.rain_mm[level]                           (8 / 30 / 65 mm)
```

Store the farmer's words and the assumed mm on the EVENT item (spec section 5). A rain check-in should replace the gridded rain for that day, not add to it. Otherwise the same rain is counted twice.

### 4.6 Paddy uses a pond model (a different branch of the engine)

Transplanted paddy is kept flooded, so the upland "D below field capacity" logic doesn't fit until the pond has gone. Add a `crop_family == "paddy"` branch that follows PAU's rule:

```text
state: pond_mm (water standing above soil), D (depletion below saturation), dry_days

water_in = rain + irrigation
if D > 0: refill D first, and the rest goes to the pond
pond     = pond + water_in - ETc - perc        perc = soils[soil].paddy_percolation_mm_per_day (only while pond > 0)
pond     = min(pond, paddy_water.bund_storage_mm)       # the rest overflows the bund
if pond < 0: D += -pond; pond = 0                       # soil starts drying
dry_days = dry_days + 1 if pond == 0 else 0

Decision (stop all advice after paddy_water.stop_irrigation_day):
  day <= continuous_ponding_days and pond < 20 mm  -> IRRIGATE to target_pond_mm
  day >  continuous_ponding_days and dry_days >= irrigate_days_after_pond_disappears
                                                   -> IRRIGATE target_pond_mm + D
  confident forecast rain >= the needed depth       -> SKIP
  otherwise                                         -> WAIT
HEAT PROTECTION for paddy = "keep 5 cm standing water" (no extra light irrigation)
```

- Treat all rain as effective up to the bund storage. The FAO 0.2 × ET0 rule is for upland soil.
- Percolation is set per soil: 8 mm/day for sandy, 5 for loam and 2 for clay (FAO). It sets how fast the pond disappears, and with it how many irrigations PAU's rule produces. Sandy fields will need many more irrigations than clay ones.

### 4.7 Energy and CO2e

```text
m3   = depth_mm x area_acres x 4.0469
kWh  = m3 x 9.81 x lift_m / (3600 x pump_eff)        # 0.827 kWh per mm per acre at 30 m, 40 %
CO2e = kWh x 0.675 kg/kWh                             # CEA v22, FY 2025-26
Rs   = kWh x 8.0 (cost to the power system, not the farmer's bill)
```

Punjab farmers pay nothing for farm power, and Haryana farmers pay 10 paise per unit. If you show rupees, label them as an estimate of the power system's cost.

### 4.8 Replay (spec 13.1)

1. Run the same weather through the Boond rules and through `baseline.json[crop]`.
2. For wheat, apply PAU's rain-delay rule: each cm of rain pushes the next irrigation back 5 days until 31 Jan, and 2 days after that. Without it the baseline is a strawman.
3. Report water, kWh, CO2e, number of irrigations and stress days (Ks < 1), labelled as a simulation.
4. Pre-sowing irrigation is identical in both runs and is not a saving.

### 4.9 Sanity check after the replay

```bash
python -m engine.check_data --weather replay/cache/ludhiana_actual_2021_22.json --crop wheat --sow 2021-11-05
```

This prints stress-free seasonal ETc and compares it with `validation_targets`. Expected ranges: wheat 280-450 mm (the real 2021-22 Ludhiana season gives 286 mm), paddy 450-650 mm (crop ET only), cotton 700-1000 mm, sugarcane 1400-2000 mm. A value far outside the range usually means an ET0 unit or date-offset bug.

### 4.10 Which crops can have live fields during the hackathon

Today is early October. In Punjab:

| Crop | Live fields possible? |
|---|---|
| Wheat | Yes. Sowing runs from late October to November |
| Autumn- or spring-planted sugarcane, and ratoons | Yes (autumn planting runs Sep–Oct: `sugarcane_autumn`) |
| Paddy | No. Transplanted June-July, now at harvest |
| Cotton | No. Sown April-May, last irrigation by 30 September |

So show paddy and cotton through the replay, using 2021 or 2022 kharif weather with a baseline from the same file. Your spec's "Must work" list is still wheat-only. The other crops are a stretch, and the FAO-56 Example 37 test is not affected by any of this data.

## 5. Assumptions register

Put this table in the README.

| # | Value | Where | Basis | Change it if… |
|---|---|---|---|---|
| A1 | Wheat Kc ini 0.40, not FAO's 0.30 | crops.wheat | Pre-sowing irrigation plus first irrigation at ~3 weeks wets the surface; PAU measured 0.39 | You want exact FAO Table 12 values |
| A2 | Wheat anthesis = heading −4 to +11 days | heat_windows | Anthesis normally follows heading by about a week; PAU gives heading days | You find a Punjab anthesis calendar |
| A3 | Paddy and cotton stage lengths = FAO proportions scaled to PAU/CICR durations | crops.paddy, crops.cotton | No Punjab lysimeter stage split found for current varieties | Local data is found |
| A4 | Rice flowering ≈ maturity − 30 days | paddy heat_windows | Standard rice physiology (ripening phase ~30 days) | — |
| A5 | Sugarcane stages 45/75/150/90 from TNAU phases | crops.sugarcane | TNAU germination/tillering/grand growth/ripening ranges | Using a UP/Punjab IISR calendar |
| A6 | Sugarcane heat 40 °C, cotton 35/38 °C | heat_windows | SASRI 2025; Oosterhuis & Snider 2011; FAO | Too many alerts (raise, or require 2 days) |
| A7 | Root growth linear to `full_depth_day` | crops.*.root_depth | Common FAO-56 practice; no single published law | — |
| A8 | Lower end of FAO Zr ranges | root_depth.maximum_m | Spec instruction; safer for scheduling | Deep, unlayered soils |
| A9 | Check-in WATERED light/normal/heavy = 50/75/100 mm | crops.*.irrigation | PAU 7.5 cm per irrigation and 10 cm pre-sowing; "light" = 2/3 | After farmer interviews |
| A10 | Check-in RAIN little/moderate/heavy = 8/30/65 mm | config.checkin | IMD light/moderate/heavy bands, deliberately low | — |
| A11 | Light (heat-protection) irrigation 40 mm, minimum advice 40 mm | config.irrigation | Smallest practical flood depth | Drip or sprinkler fields |
| A12 | Max advice 75 mm upland, 100 mm paddy | crops.*.irrigation | PAU 7.5 cm; PAU 10 cm standing-water limit | — |
| A13 | Forecast-rain confidence 70 % | config.rain | Judgement; spec asks for a configurable threshold | — |
| A14 | Pump efficiency 0.40 | config.energy | Spec default; BEE says existing pumps are inefficient | Farmer knows pump type or rating |
| A15 | Grid factor 0.675, no T&D gross-up | config.carbon | CEA v22, FY 2025-26 | CEA publishes v23 |
| A16 | Tariff Rs 8/kWh as cost of supply | config.cost | Placeholder estimate | You cite a PSERC/HERC cost-of-supply figure |
| A17 | Paddy percolation 8/5/2 mm/day; sandy loam 6 | soils.* | FAO training manual; 6 is interpolated | Local measurements |
| A18 | Paddy target pond 75 mm, bund storage 100 mm | crops.paddy.paddy_water | Within PAU's 10 cm limit | — |
| A19 | Root zone full at sowing; if no pre-sowing irrigation, start at D = RAW | config.root_zone | Spec 6.4; PAU recommends rauni | Onboarding answer |
| A20 | Baseline mid-points (5.5 weeks, 17 days, 10 days…) and rain-reset 25 mm | baseline.json | PAU/CICR give ranges, not single values | — |
| A21 | Black Vertisol FC/WP 0.40/0.22 | soils.black_vertisol | Top of FAO clay range | District soil survey data |
| A22 | Sugarcane spring planting 15 Feb-31 Mar | crops.sugarcane | AICRP / ICAR-IISR 2017: Feb–Mar in the North-West zone; the 15 Feb start is a judgement | Confirm from PAU Kharif pp. 76-95 |
| A23 | `wheat_january` stages 26/36/27/25 = 114 d and heat windows 82-95 / 90-110 | crops.wheat_january | PBW 757 matures in ~114 d; PAU 2 Dec stage split (Kaur et al. 2017) scaled | A measured stage split for January sowing |
| A24 | `sugarcane_autumn` 420 d, stages 45/210/120/45, heat window days 180-270, roots full at day 255 | crops.sugarcane_autumn | AICRP autumn planting Sep–Oct, harvest the next winter; calendar mapped for 1 Oct planting | A PAU or IISR crop calendar for autumn cane |
| A25 | Sugarcane drying-off 30 days before harvest | crops.sugar*.stop_irrigation, baseline.json | Abazied & El-Laboudy 2021 (Egypt); FAO ripening note | PAU's sugarcane chapter gives a different period |
| A26 | Cotton and sugarcane heat protection needs 2 consecutive hot days | crops.*.heat_consecutive_days | IMD heat-wave persistence; avoids daily alerts | Field feedback on alert fatigue |
| A27 | Wheat sown 21–31 Dec runs `wheat_late` (with a late-sowing warning) | data.select_profile | PAU's late window ends 20 Dec and PBW 757 is for January | — |

## 6. Not verified

- **Porter & Gawith (1999) thresholds (31 °C at anthesis, ~35 °C in grain filling).** These come from secondary citations (including PAU's Kang et al. 2017) and match your spec. I could not open the full paper.
- **Rice 35 °C at anthesis (Yoshida 1981).** This is the textbook value. The Jagadish et al. (2007) abstract confirms that the treatments were 29.6, 33.7 and 36.2 °C, but I could not read the result text.
- **PAU's cotton and sugarcane chapters (Kharif 2026, pp. 45-95).** The web reader only reached about page 30. Cotton values come from the CICR-compiled Punjab Package of Practices (2006-07) and PAU's monthly farm operations. Check the current PAU chapter before the demo.
- **IMD light and moderate rain bands.** The heavy (64.5-115.5 mm) and very heavy bands were confirmed on data.gov.in. The light and moderate bands are IMD's standard terminology but were not opened on an IMD page.
- **Garbled stage-length table in Kaur et al. 2017.** The 28 Oct row sums to 146, which matches the paper's text. The other rows are my best reading of a garbled table.
- **Open-Meteo.** I couldn't reach it from this workspace, so the seasonal ETc targets have not been run against real 2021-22 weather. Run step 4.9 once your cache exists.

## 7. Sources

**FAO**

- Allen, Pereira, Raes & Smith (1998), *FAO-56 Crop Evapotranspiration*: [Ch. 6, Tables 11-12](https://www.fao.org/4/x0490e/x0490e0b.htm), [Ch. 7, Tables 17 and 19](https://www.fao.org/4/x0490e/x0490e0c.htm), [Ch. 8, Table 22 and Example 37](https://www.fao.org/4/x0490e/x0490e0e.htm)
- FAO Land & Water crop pages: [wheat](https://www.fao.org/land-water/databases-and-software/crop-information/wheat/fr/), [cotton](https://www.fao.org/land-water/databases-and-software/crop-information/cotton/fr), [sugarcane](https://www.fao.org/land-water/databases-software/crop-information/sugarcane/en/)
- [FAO Irrigation Water Management Training Manual 3: rice saturation and percolation](https://www.fao.org/4/t7202e/t7202e07.htm)

**PAU**

- [Package of Practices, Rabi 2025-26](https://pau.edu/content/ccil/pf/pp_rabi.pdf)
- [Package of Practices, Kharif 2026](https://pau.edu/content/ccil/pf/pp_kharif.pdf)
- Farm Operations for [April](https://pau.edu/content/extserv/fo/4.pdf) and [June](https://pau.edu/content/extserv/fo/6.pdf)
- [CICR, Approved Package of Practices for Cotton, Punjab](https://static.vikaspedia.in/media/files_en/agriculture/crop-production/package-of-practices/practices-for-punjab.pdf)

**Indian field studies**

- Kaur, Gill, Kaur & Aggarwal (2017), [Estimation of crop coefficient for rice and wheat crops at Ludhiana](https://www.researchgate.net/publication/318588002_Estimation_of_crop_coefficient_for_rice_and_wheat_crops_at_Ludhiana), *J. Agrometeorology* 19(2)
- Kaur, Kingra, Singh, Kaur & Bora (2025), [Phenological and yield responses of wheat to sowing dates and varieties in Punjab](https://pub.isa-india.in/index.php/ija/article/view/7016), *Indian J. Agronomy* 70(4)
- Sharma et al. (2024), [Growth-stage specific Kc for drip wheat, Jalandhar](https://journal.agrimetassociation.org/index.php/jam/article/view/2628), *J. Agrometeorology* 26(3)
- Kang et al. (2017), [Agronomic techniques moderate terminal heat stress in wheat](https://www.ijcmas.com/6-6-2017/J.S.%20Kang,%20et%20al.pdf), PAU
- Gill et al. (2014), [Thermal requirement of wheat in Punjab](https://mausamjournal.imd.gov.in/index.php/MAUSAM/article/view/1052), *MAUSAM* 65(3)
- Singh et al. (2007), [Bt and non-Bt cotton under cotton-wheat system](https://epubs.icar.org.in/index.php/IJAgS/article/download/3371/1395/6872), *Indian J. Agric. Sci.* 77(5)

**TNAU and MPKV**

- TNAU Agritech: [sugarcane irrigation](https://agritech.tnau.ac.in/agriculture/agri_irrigationmgt_sugarcane.html), [sugarcane expert system](https://agritech.tnau.ac.in/expert_system/sugar/irrigationmanagement.html), [rice water management](https://agritech.tnau.ac.in/expert_system/paddy/cultivationpractices3.html), [puddled rice](https://agritech.tnau.ac.in/agriculture/agri_irrigationmgt_rice_transplantedpuddled.html)
- [MPKV Rahuri sugarcane recommendations](https://mpkv.ac.in/Uploads/Research/9.%20Sugarcane_20200110053812.pdf)

**Sowing windows, very late wheat, sugarcane ripening**

- AICRP on Sugarcane, Technical Bulletin No. 1 (ICAR-IISR Lucknow, 2017): North-West zone planting seasons (spring Feb–Mar, autumn Sep–Oct)
- [Varieties for late-sown irrigated wheat in Punjab](https://www.global-agriculture.com/seed-industry/varieties-suitable-for-late-sown-wheat-with-irrigated-conditions-in-punjab/) (PBW 757: about 114 days, January sowing); [Tribune: PAU guidelines for wheat sowing in January](https://www.tribuneindia.com/news/ludhiana/pau-issues-guidelines-for-wheat-sowing-in-january-to-ensure-optimal-yields/amp)
- Abazied & El-Laboudy (2021), [Effect of drying-off period on yield and quality of sugarcane](https://ejas.journals.ekb.eg/article_152335.html), *Egyptian J. Applied Sciences* 36(1):1-15

**Heat physiology**

- Porter & Gawith (1999), [Temperatures and the growth and development of wheat](https://test01.ku.dk/:obvius/pureproxy/3974268/en/publications/temperatures-and-the-growth-and-development-of-wheat-a-review), *Eur. J. Agron.* 10:23-36
- Jagadish, Craufurd & Wheeler (2007), [High temperature stress and spikelet fertility in rice](https://katalog.dhi-paris.fr/vufind/Record/NLM169633802), *J. Exp. Bot.* 58:1627
- Oosterhuis & Snider (2011), [High temperature stress on floral development and yield of cotton](https://www.cotton.org/foundation/upload/Stress-Physiology-in-Cotton_Chapter1.pdf)
- [SASRI (2025), Heat stress in sugarcane](https://sasri.org.za/article/heat-stress-in-sugarcane/)

**Energy, carbon and rainfall**

- [CEA CO2 Baseline Database v22.0 user guide](https://cea.nic.in/wp-content/uploads/baseline/2026/09/User_Guide__Version_22.0.pdf)
- [HERC 2026-27 tariff summary](https://indianstates.csis.org/articles/2026-04-01-haryana-publishes-its-tariff-order-for-2026-27/haryana-publishes-its-tariff-order-for-2026-27/)
- [PSPCL 2025-26 subsidy (Tribune)](https://www.tribuneindia.com/news/punjab/revenue-surplus-pspcl-proposes-meagre-tariff-hike-for-2025-26/amp)
- [IEA summary of BEE AgDSM](https://www.iea.org/policies/7460-agricultural-demand-side-management-agdsm-programme)
- [data.gov.in: IMD heavy-rain categories](https://www.data.gov.in/resource/stateut-wise-number-rainfall-events-country-2019-2023)
