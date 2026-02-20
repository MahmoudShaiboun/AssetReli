import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// English
import commonEn from './locales/en/common.json';
import authEn from './locales/en/auth.json';
import dashboardEn from './locales/en/dashboard.json';
import sensorsEn from './locales/en/sensors.json';
import predictionsEn from './locales/en/predictions.json';
import mlEn from './locales/en/ml.json';
import alertsEn from './locales/en/alerts.json';
import faultsEn from './locales/en/faults.json';
import settingsEn from './locales/en/settings.json';

// Arabic
import commonAr from './locales/ar/common.json';
import authAr from './locales/ar/auth.json';
import dashboardAr from './locales/ar/dashboard.json';
import sensorsAr from './locales/ar/sensors.json';
import predictionsAr from './locales/ar/predictions.json';
import mlAr from './locales/ar/ml.json';
import alertsAr from './locales/ar/alerts.json';
import faultsAr from './locales/ar/faults.json';
import settingsAr from './locales/ar/settings.json';

const resources = {
  en: {
    common: commonEn,
    auth: authEn,
    dashboard: dashboardEn,
    sensors: sensorsEn,
    predictions: predictionsEn,
    ml: mlEn,
    alerts: alertsEn,
    faults: faultsEn,
    settings: settingsEn,
  },
  ar: {
    common: commonAr,
    auth: authAr,
    dashboard: dashboardAr,
    sensors: sensorsAr,
    predictions: predictionsAr,
    ml: mlAr,
    alerts: alertsAr,
    faults: faultsAr,
    settings: settingsAr,
  },
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'en',
    defaultNS: 'common',
    ns: ['common', 'auth', 'dashboard', 'sensors', 'predictions', 'ml', 'alerts', 'faults', 'settings'],
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: 'aastreli_language',
      caches: ['localStorage'],
    },
  });

export default i18n;
