import type { Strings } from '../../i18n'

// Hindi first, simple village register. "{x}" placeholders are filled with fill().
export const strings: Strings<{
  title: string
  sim: string
  intro: string
  weatherLabel: string
  baselineLabel: string
  howTo: string
  limits: string

  boond: string
  baseline: string
  stressLine: string
  heatLimit: string
  chartTitle: string
  chartSummary: string
  thirsty: string
  rain: string
  temp: string
  warned: string
  warnedSub: string

  slider: string
  play: string
  pause: string
  back: string
  forward: string
  jumpHeat: string

  sinceSowing: string
  stage: string
  tmax: string
  rainToday: string
  noRain: string
  boondSaid: string
  watered: string
  notWatered: string
  waterLeft: string
  thirstyNow: string
  heatDay: string
  mm: string

  totalsTitle: string
  estimate: string
  water: string
  litres: string
  irrigations: string
  times: string
  power: string
  kwh: string
  co2: string
  kg: string
  stressDays: string
  days: string
  less: string
  more: string
  same: string
  none: string
  onlyBoond: string
  tableNote: string

  INITIAL: string
  TILLERING: string
  JOINTING: string
  FLOWERING: string
  GRAIN_FILLING: string
  MATURITY: string
}> = {
  hi: {
    title: '2021–22 का असली मौसम, बूँद की सलाह के साथ',
    sim: 'सिमुलेशन / simulation',
    intro:
      '{place} के पास एक जाँच वाला गेहूँ का खेत, बुवाई {sowing} को। हर दिन का मौसम असली है। खेत की मिट्टी, पानी और फ़सल का हिसाब कंप्यूटर ने लगाया है।',
    weatherLabel: 'मौसम कहाँ से',
    baselineLabel: 'किससे तुलना',
    howTo:
      'स्लाइडर खिसकाकर कोई भी दिन चुनें। नीली रेखा वह खेत है जिसने बूँद की सलाह मानी, सलेटी रेखा वह जिसमें तय तारीख़ों पर पानी दिया गया। कोई रेखा दबाव-रेखा के नीचे भूरी पट्टी में उतरे तो फ़सल प्यासी है।',
    limits:
      'ध्यान दें: इस जाँच में आगे का मौसम वही माना गया जो सच में हुआ, असली पूर्वानुमान इतना सटीक नहीं होता। पानी, बिजली और CO₂e के आँकड़े मॉडल के अनुमान हैं, खेत में नापे नहीं गए।',

    boond: 'बूँद की सलाह',
    baseline: 'तय तारीख़ों पर पानी',
    stressLine: 'दबाव-रेखा: इससे नीचे फ़सल प्यासी',
    heatLimit: 'फूल और दाने के समय गर्मी की हद',
    chartTitle: 'मिट्टी में बचा पानी',
    chartSummary:
      'पूरे मौसम में मिट्टी में बचा पानी। बूँद: {bn} बार सिंचाई, {bmm} मिमी। तय तारीख़ों वाला खेत: {fn} बार, {fmm} मिमी।',
    thirsty: 'फ़सल प्यासी',
    rain: 'बारिश',
    temp: 'दिन का सबसे ज़्यादा तापमान',
    warned: 'बूँद ने {warned} को चेताया',
    warnedSub: 'लू से {n} दिन पहले',

    slider: 'दिन चुनें',
    play: 'चलाएँ',
    pause: 'रोकें',
    back: 'एक दिन पीछे',
    forward: 'एक दिन आगे',
    jumpHeat: 'लू की चेतावनी वाला दिन',

    sinceSowing: 'बुवाई के बाद {n}वाँ दिन',
    stage: 'फ़सल',
    tmax: 'तापमान',
    rainToday: 'बारिश',
    noRain: 'नहीं',
    boondSaid: 'बूँद ने कहा',
    watered: 'आज {mm} मिमी पानी दिया',
    notWatered: 'आज पानी नहीं दिया',
    waterLeft: 'मिट्टी में पानी',
    thirstyNow: 'प्यासी',
    heatDay: 'लू',
    mm: '{v} मिमी',

    totalsTitle: '{date} तक का हिसाब',
    estimate: 'अनुमान',
    water: 'पानी',
    litres: '{v} लीटर',
    irrigations: 'सिंचाई',
    times: '{v} बार',
    power: 'पंप की बिजली',
    kwh: '{v} यूनिट',
    co2: 'कार्बन (CO₂e)',
    kg: '{v} किलो',
    stressDays: 'फ़सल प्यासी रही',
    days: '{v} दिन',
    less: 'बूँद की सलाह से {p}% कम पानी लगा। यह अनुमान है।',
    more: 'बूँद की सलाह से {p}% ज़्यादा पानी लगा। यह अनुमान है।',
    same: 'दोनों खेतों में बराबर पानी लगा। यह अनुमान है।',
    none: 'अभी तक किसी खेत में पानी नहीं दिया गया।',
    onlyBoond: 'अभी तक सिर्फ़ बूँद वाले खेत में पानी दिया गया। यह अनुमान है।',
    tableNote: 'हर पंक्ति में ऊपर बूँद, नीचे तय तारीख़ों वाला खेत।',

    INITIAL: 'अंकुर निकलना',
    TILLERING: 'कल्ले निकलना',
    JOINTING: 'गाँठ बनना',
    FLOWERING: 'बालियाँ और फूल',
    GRAIN_FILLING: 'दाना भरना',
    MATURITY: 'पकना',
  },
  en: {
    title: 'The real 2021–22 season, replayed with Boond',
    sim: 'सिमुलेशन / simulation',
    intro:
      'A test wheat field near {place}, sown on {sowing}. The weather for every day is real. The soil, water and crop are calculated by the model.',
    weatherLabel: 'Weather from',
    baselineLabel: 'Compared with',
    howTo:
      'Move the slider to pick any day. The blue line is the field that followed Boond, the grey line the field watered on fixed dates. When a line drops below the stress line into the brown band, the crop is thirsty.',
    limits:
      'Limits: in this replay the forecast is the weather that actually happened, so real forecasts will be less exact. Water, power and CO₂e figures are model estimates, not field measurements.',

    boond: 'Boond advice',
    baseline: 'Fixed dates',
    stressLine: 'Stress line: below it the crop is thirsty',
    heatLimit: 'Heat limit at flowering and grain fill',
    chartTitle: 'Water left in the soil',
    chartSummary:
      'Water left in the soil over the season. Boond: {bn} irrigations, {bmm} mm. Fixed-date field: {fn} irrigations, {fmm} mm.',
    thirsty: 'crop thirsty',
    rain: 'Rain',
    temp: 'Highest temperature of the day',
    warned: 'Boond warned on {warned}',
    warnedSub: '{n} days before the heat',

    slider: 'Pick a day',
    play: 'Play',
    pause: 'Pause',
    back: 'One day back',
    forward: 'One day forward',
    jumpHeat: 'Go to the heat warning',

    sinceSowing: 'Day {n} after sowing',
    stage: 'Crop',
    tmax: 'Temperature',
    rainToday: 'Rain',
    noRain: 'none',
    boondSaid: 'Boond said',
    watered: 'watered {mm} mm today',
    notWatered: 'did not water today',
    waterLeft: 'Water in the soil',
    thirstyNow: 'thirsty',
    heatDay: 'heat',
    mm: '{v} mm',

    totalsTitle: 'Totals up to {date}',
    estimate: 'estimate',
    water: 'Water',
    litres: '{v} litres',
    irrigations: 'Irrigations',
    times: '{v}',
    power: 'Pump power',
    kwh: '{v} kWh',
    co2: 'Carbon (CO₂e)',
    kg: '{v} kg',
    stressDays: 'Days the crop was thirsty',
    days: '{v}',
    less: 'Following Boond used {p}% less water. This is an estimate.',
    more: 'Following Boond used {p}% more water. This is an estimate.',
    same: 'Both fields used the same water. This is an estimate.',
    none: 'Neither field has been watered yet.',
    onlyBoond: 'So far only the Boond field has been watered. This is an estimate.',
    tableNote: 'In each row, Boond on top and the fixed-date field below.',

    INITIAL: 'Sprouting',
    TILLERING: 'Tillering',
    JOINTING: 'Jointing',
    FLOWERING: 'Heading and flowering',
    GRAIN_FILLING: 'Grain filling',
    MATURITY: 'Ripening',
  },
}

export type ReplayStrings = (typeof strings)['hi']
