/**
 * Validation Middleware
 */

/**
 * Validate message request
 */
exports.validateMessage = (req, res, next) => {
    const { phone, message } = req.body;
    
    if (!phone) {
        return res.status(400).json({
            success: false,
            message: 'Phone number is required'
        });
    }
    
    if (!message) {
        return res.status(400).json({
            success: false,
            message: 'Message content is required'
        });
    }
    
    next();
};

