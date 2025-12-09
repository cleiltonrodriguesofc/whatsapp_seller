
import '@testing-library/jest-dom'
import { render, screen } from '@testing-library/react'
import Home from '../app/page'

// Mock Lucide icons to avoid errors if they are not transiting well in jest environment
jest.mock('lucide-react', () => ({
    Camera: () => <div>Camera</div>,
    MessageSquare: () => <div>MessageSquare</div>,
    MoreVertical: () => <div>MoreVertical</div>,
    Phone: () => <div>Phone</div>,
    Search: () => <div>Search</div>,
}));

describe('Home Page', () => {
    it('renders the header and search', () => {
        render(<Home />)

        const heading = screen.getByRole('heading', { level: 1 })
        expect(heading).toBeInTheDocument()
        expect(heading).toHaveTextContent('WhatsApp Sales Agent')

        const searchInput = screen.getByPlaceholderText('Search or start new chat')
        expect(searchInput).toBeInTheDocument()
    })

    it('renders filter tabs', () => {
        render(<Home />)
        expect(screen.getByText('All')).toBeInTheDocument()
        expect(screen.getByText('Groups')).toBeInTheDocument()
    })
})
