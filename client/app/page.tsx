'use client';

import { useState, useEffect } from 'react';
import { Camera, MessageSquare, MoreVertical, Phone, Search } from 'lucide-react';
import ConnectionState from '@/components/ConnectionState';
// import { io } from 'socket.io-client';

export default function Home() {
  const [activeTab, setActiveTab] = useState('chats');

  // Placeholder for Sidebar
  const Sidebar = () => (
    <div className="w-[400px] flex flex-col border-r border-gray-700 bg-[var(--wa-panel-bg)]/50 backdrop-blur-xl h-full">
      {/* Header */}
      <div className="bg-[var(--wa-panel-bg)] flex flex-col border-b border-gray-800">
        <div className="h-[60px] flex items-center justify-between px-4 shrink-0">
          <div className="w-10 h-10 rounded-full bg-gray-500 overflow-hidden">
            {/* Profile Pic */}
          </div>
          <div className="flex gap-4 text-[var(--wa-text-secondary)]">
            <button><MessageSquare className="w-5 h-5" /></button>
            <button><MoreVertical className="w-5 h-5" /></button>
          </div>
        </div>
        {/* Connection Status Area */}
        <ConnectionState />
      </div>

      {/* Search */}
      <div className="h-[50px] flex items-center px-3 py-2 border-b border-gray-800">
        <div className="flex items-center gap-4 bg-[var(--wa-bg)] rounded-lg px-4 py-1.5 w-full h-full">
          <Search className="w-4 h-4 text-[var(--wa-text-secondary)]" />
          <input
            type="text"
            placeholder="Search or start new chat"
            className="bg-transparent text-sm w-full focus:outline-none text-[var(--wa-text-primary)] placeholder-[var(--wa-text-secondary)]"
          />
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex px-3 py-2 gap-2 overflow-x-auto no-scrollbar">
        {['All', 'Unread', 'Groups', 'Campaigns'].map((tab) => (
          <button
            key={tab}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${activeTab === tab
              ? 'bg-[var(--wa-primary)] text-white'
              : 'bg-[var(--wa-bg)] text-[var(--wa-text-secondary)] hover:bg-[var(--wa-header)]'
              }`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Chat List (Scrollable) */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden">
        {/* Chat Item Placeholder */}
        {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((i) => (
          <div key={i} className="flex items-center gap-3 px-3 py-3 hover:bg-[var(--wa-bg)] cursor-pointer group transition-colors">
            <div className="w-12 h-12 rounded-full bg-gray-600 shrink-0"></div>
            <div className="flex-1 min-w-0 border-b border-gray-800 pb-3 group-hover:border-transparent">
              <div className="flex justify-between items-center mb-0.5">
                <span className="text-[var(--wa-text-primary)] font-normal truncate">Contact Name {i}</span>
                <span className="text-xs text-[var(--wa-text-secondary)]">12:3{i} PM</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-[var(--wa-text-secondary)] truncate">Last message content goes here...</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  // Placeholder for Empty State / Chat Window
  const EmptyState = () => (
    <div className="flex-1 bg-[var(--wa-bg)] flex flex-col items-center justify-center border-l border-gray-700/50 relative overflow-hidden">
      {/* Decorative Background Pattern would go here */}
      <div className="text-center space-y-4 relative z-10 px-10">
        <h1 className="text-3xl font-light text-[var(--wa-text-primary)]">WhatsApp Sales Agent</h1>
        <p className="text-[var(--wa-text-secondary)] text-sm mt-4">
          Send and receive messages without keeping your phone online. <br />
          Use WhatsApp on up to 4 linked devices and 1 phone.
        </p>
        <div className="mt-10 flex items-center justify-center gap-2 text-[var(--wa-text-secondary)] text-xs">
          <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
          Waiting for backend connection...
        </div>
      </div>
    </div>
  );

  return (
    <main className="flex h-screen w-full bg-[#0c1317]">
      {/* 
        The outer container background is the very dark strip behind the chat app 
        usually seen in desktop apps, or we can just make it full screen. 
      */}
      <div className="flex w-full h-full max-w-[1700px] mx-auto overflow-hidden bg-[var(--wa-bg)] text-[var(--wa-text-primary)] shadow-2xl">
        <Sidebar />
        <EmptyState />
      </div>
    </main>
  );
}
