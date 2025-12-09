const jwt = require('jsonwebtoken');
const logger = require('../../utils/logger');

/**
 * authenticate API request
 * @param {Object} req - request object
 * @param {Object} res - response object
 * @param {Function} next - next middleware function
 */
const authenticate = (req, res, next) => {
  try {
    // Check for initial API key authentication
    if (req.path === '/api/auth') {
      const apiKey = req.body.api_key;
      
      if (!apiKey || apiKey !== process.env.API_KEY) {
        logger.warn('Invalid API key attempt');
        return res.status(401).json({ error: 'API key inválida' });
      }
      
      return next();
    }
    
    // For all other routes, check JWT token
    const authHeader = req.headers.authorization;
    
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      logger.warn('Missing or invalid authorization header');
      return res.status(401).json({ error: 'Autenticação necessária' });
    }
    
    const token = authHeader.split(' ')[1];
    
    jwt.verify(token, process.env.JWT_SECRET, (err, decoded) => {
      if (err) {
        logger.warn(`Invalid token: ${err.message}`);
        return res.status(401).json({ error: 'Token inválido ou expirado' });
      }
      
      // Add decoded data to request
      req.user = decoded;
      next();
    });
  } catch (error) {
    logger.error(`Authentication error: ${error.message}`);
    res.status(500).json({ error: 'Erro de autenticação' });
  }
};

/**
 * error handler middleware
 * @param {Object} err - error object
 * @param {Object} req - request object
 * @param {Object} res - response object
 * @param {Function} next - next middleware function
 */
const errorHandler = (err, req, res, next) => {
  logger.error(`API error: ${err.message}`);
  
  // Handle specific error types
  if (err.name === 'ValidationError') {
    return res.status(400).json({ error: err.message });
  }
  
  if (err.name === 'UnauthorizedError') {
    return res.status(401).json({ error: 'Não autorizado' });
  }
  
  // Default error response
  res.status(500).json({ error: 'Erro interno do servidor' });
};

module.exports = {
  authenticate,
  errorHandler
};
