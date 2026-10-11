import type { Strings } from '../../i18n'

// Every visible string of the Today hero. Hindi in village register first.
export const strings: Strings<{

  // Second line under the action word
  mm: string
  amount_rain_post: string
  amount_wait_pre: string
  amount_wait_days: string
  amount_wait_day: string
  no_pump_today: string

  // Reasons by reason_code
  reason_CROSSES_RAW_TODAY: string
  reason_CROSSES_RAW_TOMORROW: string
  reason_CROSSES_RAW_IN: string
  reason_BELOW_RAW: string
  reason_RAIN_COVERS: string
  reason_HEALTHY: string
  reason_HEAT_FLOWERING: string
  reason_HEAT_GRAIN_FILLING: string
  reason_HEAT: string

  // Identity line
  test_field: string
  my_field: string
  generated: string
  stale: string

  // Audio
  listen: string
  stop: string
  audio_device_voice: string
  audio_unavailable: string
  audio_failed: string
  audio_no_hindi: string

  // Facts
  facts_label: string
  rain_3d: string
  heat_risk: string
  heat_LOW: string
  heat_MEDIUM: string
  heat_HIGH: string
  heat_UNKNOWN: string
  crop: string
  crop_wheat: string
  crop_paddy: string
  crop_cotton: string
  crop_sugarcane: string
  crop_value: string
  water_est: string
  litres: string
  pump_est: string
  units: string
  co2_est: string
  co2: string
  cost_est: string
  cost: string
  unavailable_title: string
  for_area: string
  for_area_one: string

  // Stages
  stage_INITIAL: string
  stage_TILLERING: string
  stage_JOINTING: string
  stage_FLOWERING: string
  stage_GRAIN_FILLING: string
  stage_MATURITY: string

  // Soil column
  wallet_title: string
  wallet_left: string
  wallet_stress: string
  wallet_stress_note: string
  wallet_roots: string
  wallet_after: string
  wallet_aria: string
  wallet_aria_IRRIGATE: string
  wallet_aria_SKIP: string
  wallet_aria_WAIT: string
  wallet_aria_HEAT_PROTECTION: string

  // Waiting (not sown yet)
  waiting_title: string
  waiting_first_title: string
  over_title: string
  over_body: string
  waiting_first_body: string
  waiting_body: string
  waiting_days: string
  waiting_today: string
  waiting_full: string
  waiting_full_note: string
  waiting_aria: string
}> = {
  hi: {
    mm: 'मिमी',
    amount_rain_post: 'बारिश, अगले 3 दिन में',
    amount_wait_pre: 'अगला पानी लगभग',
    amount_wait_days: '{n} दिन बाद',
    amount_wait_day: '{n} दिन बाद',
    no_pump_today: 'आज पंप चलाने की ज़रूरत नहीं',

    reason_CROSSES_RAW_TODAY: 'मिट्टी की नमी आज दबाव-रेखा से नीचे जा रही है।',
    reason_CROSSES_RAW_TOMORROW: 'कल तक मिट्टी की नमी दबाव-रेखा से नीचे चली जाएगी।',
    reason_CROSSES_RAW_IN: '{n} दिन में मिट्टी की नमी दबाव-रेखा से नीचे चली जाएगी।',
    reason_BELOW_RAW: 'मिट्टी की नमी दबाव-रेखा से नीचे है, फ़सल प्यासी है।',
    reason_RAIN_COVERS: 'अगले 3 दिन में {mm} मिमी बारिश की पक्की उम्मीद है, उतना पानी काफ़ी है।',
    reason_HEALTHY: 'जड़ों के पास अभी काफ़ी नमी है।',
    reason_HEAT_FLOWERING: 'बालियाँ निकल रही हैं और तेज़ गर्मी आने वाली है।',
    reason_HEAT_GRAIN_FILLING: 'दाना भर रहा है और तेज़ गर्मी आने वाली है।',
    reason_HEAT: 'तेज़ गर्मी आने वाली है।',

    test_field: 'परीक्षण खेत',
    generated: '{date}, {time} बजे की सलाह',
    stale: 'मौसम का ताज़ा अनुमान नहीं मिला, इसलिए पिछला अनुमान इस्तेमाल हुआ है।',

    listen: 'सलाह सुनें',
    stop: 'रोकें',
    audio_device_voice: 'फ़ोन की आवाज़ में पढ़ी जाएगी',
    audio_unavailable: 'इस फ़ोन पर आवाज़ नहीं चल सकती। ऊपर लिखी सलाह पढ़ें।',
    audio_failed: 'आवाज़ नहीं चल पाई। ऊपर लिखी सलाह पढ़ें।',
    audio_no_hindi: 'इस फ़ोन में हिंदी आवाज़ नहीं है। ऊपर लिखी सलाह पढ़ें।',

    facts_label: 'आज के आँकड़े',
    rain_3d: 'अगले 3 दिन बारिश',
    heat_risk: 'गर्मी का ख़तरा',
    heat_LOW: 'कम',
    heat_MEDIUM: 'थोड़ा',
    heat_HIGH: 'ज़्यादा',
    heat_UNKNOWN: 'पता नहीं (तापमान का अनुमान नहीं मिला)',
    crop: 'फ़सल',
    crop_wheat: 'गेहूँ',
    crop_paddy: 'धान',
    crop_cotton: 'कपास',
    crop_sugarcane: 'गन्ना',
    crop_value: '{stage}, बुवाई का {n}वाँ दिन',
    water_est: 'पानी, अनुमान',
    litres: '{n} लीटर',
    pump_est: 'पंप की बिजली, अनुमान',
    units: '{n} यूनिट',
    co2_est: 'CO₂, अनुमान',
    co2: '{n} किलो',
    cost_est: 'बिजली की लागत, अनुमान (बिजली व्यवस्था पर, आपका बिल नहीं)',
    cost: '₹{n}',
    unavailable_title: 'आज की सलाह नहीं बन सकी',
    for_area: '{n} एकड़ के लिए',
    for_area_one: '{n} एकड़ के लिए',

    stage_INITIAL: 'शुरुआती बढ़वार',
    stage_TILLERING: 'वनस्पतिक बढ़वार',
    stage_JOINTING: 'तने की बढ़वार',
    stage_FLOWERING: 'फूल आने की अवस्था',
    stage_GRAIN_FILLING: 'उपज बनने की अवस्था',
    stage_MATURITY: 'पकने की अवस्था',

    wallet_title: 'जड़ों में पानी',
    wallet_left: 'पानी बचा है',
    wallet_stress: 'दबाव-रेखा',
    wallet_stress_note: 'इससे नीचे फ़सल प्यासी',
    wallet_roots: 'जड़ें {m} मीटर तक',
    wallet_after: 'पानी देने के बाद',
    wallet_aria:
      'मिट्टी का कटा हुआ हिस्सा। जड़ें {m} मीटर तक हैं। जड़ों के पास {pct}% पानी बचा है। दबाव-रेखा {stress}% पर है।',
    wallet_aria_IRRIGATE: 'पानी इस रेखा से नीचे जाने से पहले सिंचाई करें।',
    wallet_aria_SKIP: 'आने वाली बारिश इसे फिर भर देगी।',
    wallet_aria_WAIT: 'पानी अभी रेखा से ऊपर है।',
    wallet_aria_HEAT_PROTECTION: 'हल्का पानी गर्मी में फ़सल को ठंडा रखेगा।',

    my_field: 'मेरा {crop} का खेत, {area} एकड़',
    waiting_title: 'बुवाई {date} को है',
    waiting_first_title: 'पहली सलाह कल सुबह 6 बजे',
    over_title: 'इस फ़सल का मौसम पूरा हो गया',
    over_body: 'अब इस खेत के लिए सलाह नहीं आएगी। अगली फ़सल बोने पर खेत फिर से जोड़ें।',
    waiting_first_body: 'बुवाई {date} को हुई। हर सुबह मौसम देखकर बताएँगे कि पानी देना है या नहीं।',
    waiting_body: 'उस दिन से हर सुबह 6 बजे सलाह मिलेगी।',
    waiting_days: 'बुवाई में {n} दिन बाकी',
    waiting_today: 'बुवाई आज है',
    waiting_full: 'पूरी नमी',
    waiting_full_note: 'मान रहे हैं कि बुवाई से पहले पलेवा हुआ है',
    waiting_aria: 'मिट्टी का कटा हुआ हिस्सा, पूरी नमी के साथ। मान रहे हैं कि बुवाई से पहले पलेवा हुआ है।',
  },
  en: {
    mm: 'mm',
    amount_rain_post: 'of rain in the next 3 days',
    amount_wait_pre: 'Next watering in about',
    amount_wait_days: '{n} days',
    amount_wait_day: '{n} day',
    no_pump_today: 'No need to run the pump today',

    reason_CROSSES_RAW_TODAY: 'Soil moisture drops below the stress line today.',
    reason_CROSSES_RAW_TOMORROW: 'By tomorrow soil moisture will drop below the stress line.',
    reason_CROSSES_RAW_IN: 'In {n} days soil moisture will drop below the stress line.',
    reason_BELOW_RAW: 'Soil moisture is below the stress line; the crop is thirsty.',
    reason_RAIN_COVERS: '{mm} mm of rain is reliably forecast in the next 3 days. That is enough.',
    reason_HEALTHY: 'There is still plenty of water around the roots.',
    reason_HEAT_FLOWERING: 'The ears are coming out and a heat spell is on its way.',
    reason_HEAT_GRAIN_FILLING: 'The grain is filling and a heat spell is on its way.',
    reason_HEAT: 'A heat spell is on its way.',

    test_field: 'Test field',
    generated: 'Advice from {date}, {time}',
    stale: 'A fresh weather forecast was not available, so the previous one was used.',

    listen: 'Listen',
    stop: 'Stop',
    audio_device_voice: 'Read aloud by your phone’s voice',
    audio_unavailable: 'This phone cannot play the voice. Please read the advice above.',
    audio_failed: 'The voice could not play. Please read the advice above.',
    audio_no_hindi: 'This phone has no Hindi voice. Please read the advice above.',

    facts_label: 'Today’s numbers',
    rain_3d: 'Rain, next 3 days',
    heat_risk: 'Heat risk',
    heat_LOW: 'Low',
    heat_MEDIUM: 'Medium',
    heat_HIGH: 'High',
    heat_UNKNOWN: 'Unknown (no temperature forecast)',
    crop: 'Crop',
    crop_wheat: 'Wheat',
    crop_paddy: 'Paddy (Rice)',
    crop_cotton: 'Cotton',
    crop_sugarcane: 'Sugarcane',
    crop_value: '{stage}, day {n} after sowing',
    water_est: 'Water, estimate',
    litres: '{n} litres',
    pump_est: 'Pump power, estimate',
    units: '{n} units (kWh)',
    co2_est: 'CO₂, estimate',
    co2: '{n} kg',
    cost_est: 'Power cost, estimate (to the power system, not your bill)',
    cost: '₹{n}',
    unavailable_title: 'No advice today',
    for_area: 'for {n} acres',
    for_area_one: 'for {n} acre',

    stage_INITIAL: 'Early growth',
    stage_TILLERING: 'Vegetative growth',
    stage_JOINTING: 'Stem development',
    stage_FLOWERING: 'Flowering',
    stage_GRAIN_FILLING: 'Yield development',
    stage_MATURITY: 'Maturity',

    wallet_title: 'Water at the roots',
    wallet_left: 'water left',
    wallet_stress: 'Stress line',
    wallet_stress_note: 'Below this the crop is thirsty',
    wallet_roots: 'Roots reach {m} m',
    wallet_after: 'After watering',
    wallet_aria:
      'Soil cross-section. Roots reach {m} m. {pct}% of the water is left around the roots. The stress line is at {stress}%.',
    wallet_aria_IRRIGATE: 'Irrigate before it drops below the stress line.',
    wallet_aria_SKIP: 'The coming rain will refill it.',
    wallet_aria_WAIT: 'The water is still above the stress line.',
    wallet_aria_HEAT_PROTECTION: 'A light watering keeps the crop cool in the heat.',

    my_field: 'My {crop} field, {area} acres',
    waiting_title: 'Sowing is on {date}',
    waiting_first_title: 'First advice tomorrow at 6 am',
    over_title: 'This crop\'s season is over',
    over_body: 'There will be no more advice for this field. Add the field again when you sow the next crop.',
    waiting_first_body: 'Sown on {date}. Every morning we check the weather and tell you whether to water.',
    waiting_body: 'From that day you get advice every morning at 6.',
    waiting_days: '{n} days to sowing',
    waiting_today: 'Sowing is today',
    waiting_full: 'Full',
    waiting_full_note: 'Assumes a pre-sowing irrigation (palewa)',
    waiting_aria: 'Soil cross-section, full of water. Assumes a pre-sowing irrigation (palewa).',
  },
}

export type TodayStrings = (typeof strings)['hi']
