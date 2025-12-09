const { validationResult } = require('express-validator');
const logger = require('../../utils/logger');
const { 
  createScheduledMessage, 
  createScheduledMediaMessage,
  cancelScheduledMessage,
  getScheduledMessage,
  listScheduledMessages
} = require('../../services/scheduler/schedulerService');

/**
 * controller for scheduled message endpoints
 */
class ScheduleController {
  /**
   * schedule a text message
   * @param {Object} req - request object
   * @param {Object} res - response object
   */
  static async scheduleMessage(req, res) {
    try {
      // Validate request
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { to, message, scheduled_time, options } = req.body;
      const scheduledTime = new Date(scheduled_time);

      // Validate scheduled time
      if (isNaN(scheduledTime.getTime()) || scheduledTime < new Date()) {
        return res.status(400).json({ 
          error: 'Horário agendado inválido ou no passado',
          code: 'invalid_schedule_time'
        });
      }

      // Create scheduled message
      const result = await createScheduledMessage(to, message, scheduledTime, options);

      // Return response
      res.status(201).json({
        schedule_id: result.scheduleId,
        status: 'scheduled',
        scheduled_time: scheduledTime.toISOString()
      });
    } catch (error) {
      logger.error(`Error scheduling message: ${error.message}`);
      
      // Handle specific errors
      if (error.message.includes('phone')) {
        return res.status(400).json({ 
          error: 'Número de telefone inválido',
          code: 'invalid_phone'
        });
      }
      
      res.status(500).json({ error: 'Erro ao agendar mensagem' });
    }
  }

  /**
   * schedule a media message
   * @param {Object} req - request object
   * @param {Object} res - response object
   */
  static async scheduleMediaMessage(req, res) {
    try {
      // Validate request
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { to, caption, media_type, media_url, scheduled_time, options } = req.body;
      const scheduledTime = new Date(scheduled_time);

      // Validate scheduled time
      if (isNaN(scheduledTime.getTime()) || scheduledTime < new Date()) {
        return res.status(400).json({ 
          error: 'Horário agendado inválido ou no passado',
          code: 'invalid_schedule_time'
        });
      }

      // Create scheduled message
      const result = await createScheduledMediaMessage(
        to, 
        media_url, 
        caption, 
        media_type, 
        scheduledTime, 
        options
      );

      // Return response
      res.status(201).json({
        schedule_id: result.scheduleId,
        status: 'scheduled',
        scheduled_time: scheduledTime.toISOString()
      });
    } catch (error) {
      logger.error(`Error scheduling media message: ${error.message}`);
      
      // Handle specific errors
      if (error.message.includes('phone')) {
        return res.status(400).json({ 
          error: 'Número de telefone inválido',
          code: 'invalid_phone'
        });
      }
      
      if (error.message.includes('media')) {
        return res.status(400).json({ 
          error: 'Mídia inválida ou inacessível',
          code: 'invalid_media'
        });
      }
      
      res.status(500).json({ error: 'Erro ao agendar mensagem com mídia' });
    }
  }

  /**
   * schedule bulk messages
   * @param {Object} req - request object
   * @param {Object} res - response object
   */
  static async scheduleBulkMessages(req, res) {
    try {
      // Validate request
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { contacts, message, scheduled_time, options } = req.body;
      const scheduledTime = new Date(scheduled_time);

      // Validate scheduled time
      if (isNaN(scheduledTime.getTime()) || scheduledTime < new Date()) {
        return res.status(400).json({ 
          error: 'Horário agendado inválido ou no passado',
          code: 'invalid_schedule_time'
        });
      }

      // Validate contacts
      const invalidContacts = [];
      const validContacts = contacts.filter(contact => {
        const isValid = contact.match(/^\d+$/);
        if (!isValid) invalidContacts.push(contact);
        return isValid;
      });

      // Create batch schedule ID
      const batchScheduleId = `bsched_${Date.now()}_${Math.random().toString(36).substring(2, 15)}`;

      // Schedule messages for each contact
      // In a real implementation, this would use a batch scheduling service
      for (const contact of validContacts) {
        await createScheduledMessage(contact, message, scheduledTime, { 
          ...options, 
          batchScheduleId 
        });
      }

      // Return response
      res.status(201).json({
        batch_schedule_id: batchScheduleId,
        status: 'scheduled',
        scheduled_time: scheduledTime.toISOString(),
        contact_count: validContacts.length
      });
    } catch (error) {
      logger.error(`Error scheduling bulk messages: ${error.message}`);
      res.status(500).json({ error: 'Erro ao agendar mensagens em massa' });
    }
  }

  /**
   * cancel a scheduled message
   * @param {Object} req - request object
   * @param {Object} res - response object
   */
  static async cancelScheduledMessage(req, res) {
    try {
      const { schedule_id } = req.params;

      // Cancel scheduled message
      const result = await cancelScheduledMessage(schedule_id);

      // Return response
      res.status(200).json({
        success: true,
        message: 'Agendamento cancelado com sucesso'
      });
    } catch (error) {
      logger.error(`Error cancelling scheduled message: ${error.message}`);
      
      if (error.message.includes('not found')) {
        return res.status(404).json({ error: 'Agendamento não encontrado' });
      }
      
      res.status(500).json({ error: 'Erro ao cancelar agendamento' });
    }
  }

  /**
   * list scheduled messages
   * @param {Object} req - request object
   * @param {Object} res - response object
   */
  static async listScheduledMessages(req, res) {
    try {
      const { status, page = 1, limit = 20 } = req.query;

      // Build filters
      const filters = {};
      if (status) {
        filters.status = status;
      }

      // Get scheduled messages
      const result = await listScheduledMessages(filters, parseInt(page), parseInt(limit));

      // Return response
      res.status(200).json(result);
    } catch (error) {
      logger.error(`Error listing scheduled messages: ${error.message}`);
      res.status(500).json({ error: 'Erro ao listar agendamentos' });
    }
  }
}

module.exports = ScheduleController;
