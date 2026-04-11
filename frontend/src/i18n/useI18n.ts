import { useUIPreferencesStore } from '../store/uiPreferences';

const phraseMap: Record<string, string> = {
  Home: 'Αρχική',
  Dashboard: 'Πίνακας',
  Settings: 'Ρυθμίσεις',
  'Admin Hub': 'Κέντρο Διαχείρισης',
  CRM: 'CRM',
  Clients: 'Πελάτες',
  Pipeline: 'Ροή Αιτήσεων',
  Hierarchy: 'Ιεραρχία',
  Commissions: 'Προμήθειες',
  Security: 'Ασφάλεια',
  'Client Area': 'Περιοχή Πελάτη',
  'IB Portal': 'Πύλη IB',
  Applications: 'Αιτήσεις',
  Tokens: 'Κουπόνια',
  'Tier Rates': 'Ποσοστά Επιπέδων',
  Cockpit: 'Κονσόλα',
  Execute: 'Εκτέλεση',
  Research: 'Έρευνα',
  System: 'Σύστημα',
  'Command palette': 'Παλέτα εντολών',
  'Jump anywhere with keyboard-first navigation': 'Μετακίνηση παντού με πληκτρολόγιο',
  'Trading desk': 'Πίνακας συναλλαγών',
  'dYdX Arbitrage OS': 'dYdX Arbitrage OS',
  'Research, backtests, bots, and controls': 'Έρευνα, backtests, bots και έλεγχοι',
  'Workspace ready': 'Ο χώρος εργασίας είναι έτοιμος',
  'Signed in as': 'Συνδεδεμένος ως',
  Logout: 'Αποσύνδεση',
  'Live desk': 'Ζωντανός πίνακας',
  Environment: 'Περιβάλλον',
  Development: 'Ανάπτυξη',
  Production: 'Παραγωγή',
  Network: 'Δίκτυο',
  Online: 'Συνδεδεμένο',
  Offline: 'Εκτός σύνδεσης',
  'Local time': 'Τοπική ώρα',
  Operator: 'Χειριστής',
  'Jump anywhere': 'Μεταπήδηση παντού',
  Trader: 'Trader',
  'Move across live workflows with route context, command access, and operational state in view.':
    'Μετακινηθείτε σε ζωντανές ροές με ορατό context διαδρομής, πρόσβαση εντολών και λειτουργική κατάσταση.',
};

export const useI18n = () => {
  const language = useUIPreferencesStore((state) => state.language);

  const t = (en: string, el: string) => (language === 'el' ? el : en);

  const tr = (text: string): string => {
    if (language !== 'el') return text;
    return phraseMap[text] ?? text;
  };

  const locale = language === 'el' ? 'el-GR' : 'en-US';

  return { language, locale, t, tr };
};
