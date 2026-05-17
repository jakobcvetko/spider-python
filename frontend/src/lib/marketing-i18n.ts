export type MarketingLocale = 'sl' | 'en'

export const MARKETING_LOCALE_STORAGE_KEY = 'spider_marketing_locale'

export type MarketingCopy = {
  brandTagline: string
  signIn: string
  createAccount: string
  back: string
  switchToEnglish: string
  switchToSlovenian: string
  landing: {
    heroEyebrow: string
    heroTitle: string
    heroBody: string
    sourceBolha: string
    sourceAvtonet: string
    sourceScrapers: string
    sectionOneLabel: string
    sectionOneTitle: string
    sectionOneBody: string
    featureCarsTitle: string
    featureCarsBody: string
    featureGoodsTitle: string
    featureGoodsBody: string
    featureMatchesTitle: string
    featureMatchesBody: string
    sectionHowLabel: string
    sectionHowTitle: string
    sectionHowBody: string
    step1Title: string
    step1Body: string
    step2Title: string
    step2Body: string
    step3Title: string
    step3Body: string
    ctaTitle: string
    ctaBody: string
    ctaButton: string
    footer: string
  }
  login: {
    title: string
    description: string
    email: string
    password: string
    submit: string
    noAccount: string
    createAccountLink: string
    errorFallback: string
  }
  register: {
    title: string
    description: string
    email: string
    businessName: string
    password: string
    passwordHint: string
    submit: string
    hasAccount: string
    signInLink: string
    errorFallback: string
  }
}

export const marketingCopy: Record<MarketingLocale, MarketingCopy> = {
  sl: {
    brandTagline: 'Inteligenca za trgovce',
    signIn: 'Prijava',
    createAccount: 'Ustvari račun',
    back: 'Nazaj',
    switchToEnglish: 'English',
    switchToSlovenian: 'Slovenščina',
    landing: {
      heroEyebrow: 'Za avtohiše in trgovce',
      heroTitle: 'Prave objave najdete prej kot konkurenca.',
      heroBody:
        'Spider nenehno spremlja Bolha in avto.net ter vam pokaže vozila in blago, ki ustrezajo vašim pravilih nakupa.',
      sourceBolha: 'Bolha',
      sourceAvtonet: 'avto.net',
      sourceScrapers: 'Prilagojeni pajki',
      sectionOneLabel: 'En vir',
      sectionOneTitle: 'Dva portala. Brez skakanja med zavihki.',
      sectionOneBody:
        'Ne glede na to, ali odkupujete avtomobile ali večje količine blaga — novi oglasi pridejo na eno mesto, filtrirani po tem, kar res želite kupiti.',
      featureCarsTitle: 'Osebna vozila in kombi',
      featureCarsBody:
        'Model, letnik, kilometrina, cenovni razpon — nastavljeno za odkup na avto.net in Bolhi.',
      featureGoodsTitle: 'Oprema in blago',
      featureGoodsBody:
        'Stroji, palete, presežne zaloge — pravila po ključnih besedah in kategorijah za trgovce.',
      featureMatchesTitle: 'Sveži zadetki vsak dan',
      featureMatchesBody:
        'Preglejte včerajšnje in današnje ujemanja brez celodnevnega osveževanja oglasov.',
      sectionHowLabel: 'Kako deluje',
      sectionHowTitle: 'Pajke nastavite enkrat. Mi spremljamo naprej.',
      sectionHowBody:
        'Določite, kaj iščete — znamko, zgornjo ceno, ključne besede. Spider zajema nove oglase, preveri pravila in zadetke pripravi v vašem pregledu.',
      step1Title: 'Ustvarite pajke',
      step1Body: 'Za vsak vir in vsak profil nakupa.',
      step2Title: 'Spremljamo oglase',
      step2Body: 'Nenehno zajemanje in ujemanje.',
      step3Title: 'Preglejte zadetke',
      step3Body: 'Ukrepajte, preden oglas izgine.',
      ctaTitle: 'Ste pripravljeni nehat ročno osveževati oglase?',
      ctaBody: 'Brezplačen račun. Prvega pajka nastavite v nekaj minutah.',
      ctaButton: 'Ustvari račun trgovca',
      footer: 'Spider — obveščanje o malih oglasih za slovenske trgovce',
    },
    login: {
      title: 'Prijava',
      description: 'Dostop do nadzorne plošče, zadetkov in pajkov.',
      email: 'E-pošta',
      password: 'Geslo',
      submit: 'Prijava',
      noAccount: 'Nov uporabnik?',
      createAccountLink: 'Ustvari račun',
      errorFallback: 'Prijava ni uspela',
    },
    register: {
      title: 'Ustvari račun',
      description: 'V nekaj minutah nastavite pajke za Bolha in avto.net.',
      email: 'E-pošta',
      businessName: 'Ime podjetja ali salona (neobvezno)',
      password: 'Geslo',
      passwordHint: 'Uporabite najmanj 8 znakov.',
      submit: 'Ustvari račun',
      hasAccount: 'Že imate račun?',
      signInLink: 'Prijava',
      errorFallback: 'Računa ni bilo mogoče ustvariti',
    },
  },
  en: {
    brandTagline: 'Dealer intel',
    signIn: 'Sign in',
    createAccount: 'Create account',
    back: 'Back',
    switchToEnglish: 'English',
    switchToSlovenian: 'Slovenščina',
    landing: {
      heroEyebrow: 'For car dealers & traders',
      heroTitle: 'Catch the right listings before your competitor does.',
      heroBody:
        'Spider watches Bolha and avto.net around the clock and surfaces vehicles and goods that match your buying rules.',
      sourceBolha: 'Bolha',
      sourceAvtonet: 'avto.net',
      sourceScrapers: 'Custom scrapers',
      sectionOneLabel: 'One feed',
      sectionOneTitle: 'Two marketplaces. Zero tab-hopping.',
      sectionOneBody:
        'Whether you flip cars or buy stock in bulk, new ads land in one place — filtered to what you actually want to buy.',
      featureCarsTitle: 'Cars & vans',
      featureCarsBody:
        'Model, year, mileage, price band — tuned for lot buyers on avto.net and Bolha.',
      featureGoodsTitle: 'Equipment & goods',
      featureGoodsBody:
        'Machinery, pallets, retail overstock — keyword and category rules for traders.',
      featureMatchesTitle: 'Fresh matches daily',
      featureMatchesBody:
        'See what matched yesterday and today without refreshing classifieds all day.',
      sectionHowLabel: 'How it works',
      sectionHowTitle: 'Set scrapers once. We keep polling.',
      sectionHowBody:
        'Define what you are hunting for — make, price ceiling, keywords. Spider ingests new listings, runs your rules, and lines up matches in your inbox view.',
      step1Title: 'Create scrapers',
      step1Body: 'Per source, per buying profile.',
      step2Title: 'We monitor listings',
      step2Body: 'Continuous scrape and match pipeline.',
      step3Title: 'Review matches',
      step3Body: 'Act on fresh stock before it is gone.',
      ctaTitle: 'Ready to stop refreshing classifieds?',
      ctaBody: 'Free account. Set up your first scraper in minutes.',
      ctaButton: 'Create dealer account',
      footer: 'Spider — classified intelligence for Slovenian dealers',
    },
    login: {
      title: 'Sign in',
      description: 'Access your dashboard, matches, and scrapers.',
      email: 'Email',
      password: 'Password',
      submit: 'Sign in',
      noAccount: 'New dealer?',
      createAccountLink: 'Create an account',
      errorFallback: 'Could not sign in',
    },
    register: {
      title: 'Create account',
      description: 'Set up scrapers for Bolha and avto.net in minutes.',
      email: 'Email',
      businessName: 'Dealership or business name (optional)',
      password: 'Password',
      passwordHint: 'Use at least 8 characters.',
      submit: 'Create account',
      hasAccount: 'Already have an account?',
      signInLink: 'Sign in',
      errorFallback: 'Could not create account',
    },
  },
}

export function readStoredMarketingLocale(): MarketingLocale {
  try {
    const stored = localStorage.getItem(MARKETING_LOCALE_STORAGE_KEY)
    return stored === 'en' ? 'en' : 'sl'
  } catch {
    return 'sl'
  }
}
