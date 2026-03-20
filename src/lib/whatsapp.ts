const WHATSAPP_NUMBER = '233208126447';

export function createWhatsAppLink(message: string) {
  return `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(message)}`;
}

export function registerWhatsAppLink(course?: string) {
  return createWhatsAppLink(
    course
      ? `Hello Make Up & More, I want to register for ${course}.`
      : 'Hello Make Up & More, I want to register for a course.'
  );
}

export function reserveClassWhatsAppLink(course: string) {
  return createWhatsAppLink(
    `Hello Make Up & More, I want to reserve a slot for the upcoming ${course} class.`
  );
}

export function productWhatsAppLink(product: string) {
  return createWhatsAppLink(
    `Hello Make Up & More, I want to buy/enquire about ${product}.`
  );
}
