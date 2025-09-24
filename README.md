# 🤖 Advanced Telegram Bot Shop System

A comprehensive, enterprise-grade Telegram bot system for e-commerce operations with advanced features including VIP management, automated advertising, stock tracking, and referral programs.

## 🚀 Features

### 🛍️ **Core E-commerce**
- **Multi-location Product Management** - Cities, districts, product types
- **Shopping Cart System** - Add, remove, modify items
- **Secure Payment Processing** - NOWPayments integration with multiple cryptocurrencies
- **Inventory Management** - Real-time stock tracking with reservations
- **Order History** - Complete purchase tracking

### 👑 **VIP & Customer Management**
- **Customizable VIP Levels** - Create custom tiers (Diamond Customer, Platinum Member, etc.)
- **Automatic Level Progression** - Based on purchase count
- **VIP Benefits System** - Discounts, perks, exclusive access
- **Customer Analytics** - Track customer lifetime value

### 🎁 **Marketing & Growth**
- **Referral Program** - Reward customers for bringing friends
- **Discount Code System** - Flexible promotional codes
- **Auto Ads System** - Automated advertising campaigns
- **A/B Testing Framework** - Optimize user experience
- **Broadcast System** - Targeted messaging

### 📊 **Business Intelligence**
- **Real-time Analytics** - Sales, revenue, customer metrics
- **Stock Management** - Low stock alerts, inventory reports
- **Financial Reporting** - Revenue tracking and analysis
- **Customer Segmentation** - VIP, regular, new customer analysis

### 🔧 **Admin Features**
- **Organized Admin Panel** - Categorized management interface
- **Bulk Operations** - Mass product management
- **User Management** - Search, ban, adjust balances
- **System Monitoring** - Health checks and alerts

## 🛠️ Installation

### Prerequisites
- Python 3.11+
- SQLite3
- Telegram Bot Token
- NOWPayments API Key (for crypto payments)

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/goblin987/ioioioioioiio.git
cd ioioioioioiio
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment**
Create a `.env` file with:
```env
TOKEN=your_telegram_bot_token
ADMIN_ID=your_telegram_user_id
NOWPAYMENTS_API_KEY=your_nowpayments_api_key
WEBHOOK_URL=your_webhook_url
```

4. **Run the bot**
```bash
python main.py
```

## 📋 Configuration

### Admin Setup
1. Start the bot and use `/admin` command
2. Configure cities, districts, and product types
3. Add products through the admin panel
4. Set up VIP levels and benefits
5. Configure payment methods

### VIP System Setup
1. Access `Admin Menu → User Management → VIP System`
2. Create custom VIP levels with names and emojis
3. Set purchase requirements for each level
4. Configure benefits and discounts
5. Monitor customer progression

## 🎯 System Architecture

### Core Modules
- **`main.py`** - Bot initialization and routing
- **`user.py`** - User interface and shopping flow
- **`admin.py`** - Admin panel and management
- **`payment.py`** - Payment processing and crypto integration
- **`utils.py`** - Database, utilities, and helper functions

### Advanced Features
- **`vip_system.py`** - VIP levels and customer ranking
- **`referral_system.py`** - Referral program management
- **`auto_ads_system.py`** - Automated advertising campaigns
- **`ab_testing.py`** - A/B testing framework
- **`stock_management.py`** - Inventory tracking and alerts

### Database Schema
- **Users** - Customer data, balances, VIP status
- **Products** - Inventory with locations and media
- **Purchases** - Order history and analytics
- **VIP Levels** - Customizable ranking system
- **Campaigns** - Marketing automation
- **Referrals** - Customer acquisition tracking

## 🔐 Security Features

- **Admin Authorization** - Multi-level admin access
- **Input Validation** - Secure data handling
- **Payment Verification** - NOWPayments integration
- **Audit Logging** - Complete action tracking
- **Rate Limiting** - Spam and abuse prevention

## 📈 Business Benefits

### For Customers
- **Easy Shopping** - Intuitive Telegram interface
- **VIP Rewards** - Progression and benefits system
- **Referral Earnings** - Get paid for referrals
- **Secure Payments** - Cryptocurrency integration

### For Business Owners
- **Automated Operations** - Reduce manual work
- **Customer Insights** - Data-driven decisions
- **Growth Tools** - Referrals, ads, A/B testing
- **Scalable Platform** - Handle high traffic volumes

## 🎮 VIP System Highlights

### Default VIP Levels
- 🌱 **New Customer** (0-2 purchases) - Welcome bonuses
- ⭐ **Regular Customer** (3-9 purchases) - 2% discount
- 👑 **VIP Customer** (10-24 purchases) - 5% discount, priority support
- 💎 **Diamond Customer** (25+ purchases) - 10% discount, exclusive access

### Customization Options
- **Custom Level Names** - "Diamond Elite", "Platinum Member", etc.
- **Custom Emojis** - Any emoji for level representation
- **Flexible Requirements** - Set exact purchase thresholds
- **Custom Benefits** - Define unique perks per level
- **Dynamic Discounts** - Percentage-based VIP pricing

## 🚀 Advanced Features

### Marketing Automation
- **Campaign Scheduling** - Automated ad posting
- **Target Audience** - Location, status, behavior-based
- **Performance Tracking** - Campaign analytics
- **A/B Testing** - Optimize messaging and UI

### Stock Management
- **Real-time Tracking** - Live inventory updates
- **Low Stock Alerts** - Automated admin notifications
- **Reservation System** - Prevent overselling
- **Bulk Operations** - Efficient inventory management

### Analytics Dashboard
- **Sales Reports** - Revenue, units, trends
- **Customer Analytics** - VIP distribution, behavior
- **Geographic Analysis** - City/district performance
- **Financial Tracking** - Profit, costs, margins

## 📞 Support

For support and customization requests, contact the development team through the bot's admin panel or GitHub issues.

## 📄 License

This project is proprietary software. All rights reserved.

---

**Built for high-traffic e-commerce operations with enterprise-grade features and scalability.**
