
import '@testing-library/jest-dom'
import { render, screen, act } from '@testing-library/react'
import ConnectionState from '../components/ConnectionState'

// Mock useSocket hook
const mockSocketChange = jest.fn();
const mockEmit = jest.fn();
const mockOn = jest.fn();

jest.mock('../app/hooks/useSocket', () => ({
    useSocket: () => ({
        socket: {
            on: mockOn,
            emit: mockEmit,
            off: jest.fn()
        },
        isConnected: true
    })
}));

describe('ConnectionState Component', () => {
    beforeEach(() => {
        mockOn.mockClear();
    });

    it('renders status when connected', () => {
        render(<ConnectionState />)
        expect(screen.getByText(/Status:/i)).toBeInTheDocument()
        expect(screen.getByText(/disconnected/i)).toBeInTheDocument()
    })

    // More complex tests would require mocking 'on' callback execution
})
