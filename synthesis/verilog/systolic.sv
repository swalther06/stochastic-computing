// SHIFT: shift register (parameterizable depth and data width)
module shift_reg #(parameter DEPTH = 4, parameter W = 1) (
    input              clk, rst,
    input  [W-1:0]     d,
    output [W-1:0]     q
);
    reg [W-1:0] sr [0:DEPTH-1];
    assign q = sr[DEPTH-1];
    always_ff @(posedge clk) begin
        if (rst) begin
            for (int i = 0; i < DEPTH; i++) sr[i] <= '0;
        end else begin
            for (int i = DEPTH-1; i > 0; i--) sr[i] <= sr[i-1];
            sr[0] <= d;
        end
    end
endmodule

// FIFO: synchronous FIFO (parameterizable depth and data width)
module sc_fifo #(parameter DEPTH = 4, parameter W = 1) (
    input              clk, rst,
    input              wr_en, rd_en,
    input  [W-1:0]     din,
    output reg [W-1:0] dout,
    output             full, empty
);
    reg [W-1:0]              mem [0:DEPTH-1];
    reg [$clog2(DEPTH):0]    count;
    reg [$clog2(DEPTH)-1:0]  wr_ptr, rd_ptr;

    assign full  = (count == DEPTH);
    assign empty = (count == 0);

    always_ff @(posedge clk) begin
        if (rst) begin
            wr_ptr <= 0; rd_ptr <= 0; count <= 0; dout <= '0;
        end else begin
            if (wr_en && !full)  begin mem[wr_ptr] <= din;      wr_ptr <= wr_ptr + 1; count <= count + 1; end
            if (rd_en && !empty) begin dout <= mem[rd_ptr]; rd_ptr <= rd_ptr + 1; count <= count - 1; end
        end
    end
endmodule

// SEL: stochastic selector — gates input bitstream with control stream
module sel_unit (
    input  sel, a, b
    output y
);
    assign y = sel ? b : a;
endmodule
