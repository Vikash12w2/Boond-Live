import type { Strings } from '../../i18n'

export const strings: Strings<{
  title: string
  intro: string
  day: string
  today: string
  yesterday: string
  watered: string
  rained: string
  light: string
  normal: string
  heavy: string
  little: string
  moderate: string
  heavyRain: string
  saving: string
  savedToday: string
  savedYesterday: string
  failed: string
}> = {
  hi: {
    title: 'खेत में क्या हुआ?',
    intro: 'पानी दिया या बारिश हुई तो यहाँ बताएँ। बूँद मिट्टी का हिसाब ठीक कर लेगा।',
    day: 'कब',
    today: 'आज',
    yesterday: 'कल',
    watered: 'मैंने पानी दिया',
    rained: 'बारिश हुई',
    light: 'हल्का',
    normal: 'सामान्य',
    heavy: 'भारी',
    little: 'थोड़ी',
    moderate: 'ठीक-ठाक',
    heavyRain: 'तेज़',
    saving: 'दर्ज कर रहे हैं…',
    savedToday: 'दर्ज हो गया। आज का पानी कल सुबह की सलाह में गिना जाएगा।',
    savedYesterday: 'दर्ज हो गया। आज की सलाह इसके हिसाब से बदल दी गई है।',
    failed: 'दर्ज नहीं हो सका ({msg})। फिर कोशिश करें।',
  },
  en: {
    title: 'What happened in the field?',
    intro: 'Tell Boond when you water or it rains, so it can correct the soil balance.',
    day: 'When',
    today: 'Today',
    yesterday: 'Yesterday',
    watered: 'I watered',
    rained: 'It rained',
    light: 'Light',
    normal: 'Normal',
    heavy: 'Heavy',
    little: 'A little',
    moderate: 'Moderate',
    heavyRain: 'Heavy',
    saving: 'Saving…',
    savedToday: 'Saved. Today\'s water counts in tomorrow morning\'s advice.',
    savedYesterday: 'Saved. Today\'s advice has been updated for it.',
    failed: 'Could not save ({msg}). Please try again.',
  },
}
