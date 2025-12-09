const isOperatingHours = () => {
  const now = new Date();
  const hour = now.getHours();
  
  const startHour = parseInt(process.env.OPERATION_START_HOUR || '7');
  const endHour = parseInt(process.env.OPERATION_END_HOUR || '23');
  
  return hour >= startHour && hour < endHour;
};

const getNextOperatingWindowStart = () => {
  const now = new Date();
  const startHour = parseInt(process.env.OPERATION_START_HOUR || '7');
  
  // If we're before today's start time, return today's start time
  if (now.getHours() < startHour) {
    const startTime = new Date(now);
    startTime.setHours(startHour, 0, 0, 0);
    return startTime.getTime();
  }
  
  // Otherwise, return tomorrow's start time
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  tomorrow.setHours(startHour, 0, 0, 0);
  return tomorrow.getTime();
};

const generateRandomDelay = (messageLength) => {
  // Base typing speed: 5 characters per second
  const baseDelay = messageLength * 200;
  
  // Add randomness: +/- 30%
  const randomFactor = 0.7 + (Math.random() * 0.6); // 0.7 to 1.3
  
  // Ensure minimum delay of 500ms and maximum of 5000ms
  return Math.min(Math.max(Math.round(baseDelay * randomFactor), 500), 5000);
};

const formatPhoneNumber = (phoneNumber) => {
  // Remove any non-digit characters
  let cleaned = phoneNumber.replace(/\D/g, '');
  
  // Ensure it has country code (default to Brazil +55 if none)
  if (cleaned.length <= 13 && !cleaned.startsWith('55')) {
    cleaned = '55' + cleaned;
  }
  
  // Add @c.us suffix if not present
  if (!phoneNumber.endsWith('@c.us')) {
    cleaned = cleaned + '@c.us';
  }
  
  return cleaned;
};

module.exports = {
  isOperatingHours,
  getNextOperatingWindowStart,
  generateRandomDelay,
  formatPhoneNumber
};
