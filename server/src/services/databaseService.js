
const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

class DatabaseService {
    constructor() {
        const dbPath = path.resolve(__dirname, '../../database.sqlite');
        this.db = new Database(dbPath, { verbose: console.log });
        this.initialize();
    }

    initialize() {
        // Create Contacts Table
        this.db.prepare(`
            CREATE TABLE IF NOT EXISTS contacts (
                id TEXT PRIMARY KEY,
                name TEXT,
                number TEXT,
                pushname TEXT,
                isMyContact INTEGER DEFAULT 0,
                profilePicUrl TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        `).run();

        // Create Campaigns Table
        this.db.prepare(`
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT DEFAULT 'pending', -- pending, active, completed, paused
                type TEXT DEFAULT 'message', -- message, status (story)
                scheduled_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        `).run();

        // Create Campaign Items (Recipients)
        this.db.prepare(`
            CREATE TABLE IF NOT EXISTS campaign_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER,
                contact_id TEXT,
                status TEXT DEFAULT 'pending', -- pending, sent, failed
                sent_at DATETIME,
                FOREIGN KEY(campaign_id) REFERENCES campaigns(id),
                FOREIGN KEY(contact_id) REFERENCES contacts(id)
            )
        `).run();

        // Create Schedules (For simple status updates or recurring tasks)
        this.db.prepare(`
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL, -- status_update, message_blast
                content TEXT, -- Image URL or Text
                cron_expression TEXT,
                is_active INTEGER DEFAULT 1,
                last_run_at DATETIME
            )
        `).run();

        console.log('Database initialized successfully');
    }

    // Contact Methods
    saveContact(contact) {
        const stmt = this.db.prepare(`
            INSERT OR REPLACE INTO contacts (id, name, number, pushname, isMyContact, profilePicUrl)
            VALUES (@id, @name, @number, @pushname, @isMyContact, @profilePicUrl)
        `);
        return stmt.run(contact);
    }

    getContacts() {
        return this.db.prepare('SELECT * FROM contacts').all();
    }

    // Campaign Methods
    createCampaign(campaign) {
        const stmt = this.db.prepare(`
            INSERT INTO campaigns (name, message, status, type, scheduled_at, audience_type)
            VALUES (@name, @message, @status, @type, @scheduled_at, @audience_type)
        `);
        return stmt.run(campaign);
    }

    updateCampaignStatus(id, status) {
        const stmt = this.db.prepare('UPDATE campaigns SET status = ? WHERE id = ?');
        return stmt.run(status, id);
    }

    getCampaigns() {
        // Ensure audience_type column exists (simple migration)
        try {
            this.db.prepare("ALTER TABLE campaigns ADD COLUMN audience_type TEXT DEFAULT 'all'").run();
        } catch (error) {
            // Column likely exists
        }
        return this.db.prepare('SELECT * FROM campaigns ORDER BY created_at DESC').all();
    }

    getCampaignItems(campaignId) {
        return this.db.prepare(`
            SELECT ci.*, c.number, c.name 
            FROM campaign_items ci
            JOIN contacts c ON ci.contact_id = c.id
            WHERE ci.campaign_id = ?
        `).all(campaignId);
    }
}

module.exports = new DatabaseService();
