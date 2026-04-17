import { configureStore, createSlice, PayloadAction } from '@reduxjs/toolkit';

interface MT5State {
   status: 'DISCONNECTED' | 'CONNECTING' | 'CONNECTED';
   credentials: { accountID: string; password: string; server: string };
   autoTrading: boolean;
}

const initialState: MT5State = {
   status: 'DISCONNECTED',
   credentials: { accountID: '', password: '', server: '' },
   autoTrading: false,
};

export const mt5Slice = createSlice({
  name: 'mt5',
  initialState,
  reducers: {
    setMt5Status: (state, action: PayloadAction<'DISCONNECTED' | 'CONNECTING' | 'CONNECTED'>) => {
        state.status = action.payload;
    },
    setCredentials: (state, action: PayloadAction<MT5State['credentials']>) => {
        state.credentials = action.payload;
    },
    setAutoTrading: (state, action: PayloadAction<boolean>) => {
        state.autoTrading = action.payload;
    }
  }
});

export const { setMt5Status, setCredentials, setAutoTrading } = mt5Slice.actions;

export const store = configureStore({
  reducer: {
    mt5: mt5Slice.reducer
  }
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
