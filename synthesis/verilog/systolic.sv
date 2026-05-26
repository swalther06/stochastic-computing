// SHIFT: 1-bit shift register (parameterizable depth)
module shift_reg #(parameter DEPTH = 4) (
    input  clk, rst, d,
    output q
);
    reg [DEPTH-1:0] sr;
    assign q = sr[DEPTH-1];
    always_ff @(posedge clk) begin
        if (rst) sr <= 0;
        else     sr <= {sr[DEPTH-2:0], d};
    end
endmodule

// FIFO: 1-bit synchronous FIFO
module sc_fifo #(parameter DEPTH = 4) (
    input              clk, rst,
    input              wr_en, rd_en, din,
    output reg         dout,
    output             full, empty
);
    reg [DEPTH-1:0]          mem;
    reg [$clog2(DEPTH):0]    count;
    reg [$clog2(DEPTH)-1:0]  wr_ptr, rd_ptr;

    assign full  = (count == DEPTH);
    assign empty = (count == 0);

    always_ff @(posedge clk) begin
        if (rst) begin
            wr_ptr <= 0; rd_ptr <= 0; count <= 0; dout <= 0;
        end else begin
            if (wr_en && !full)  begin mem[wr_ptr] <= din;      wr_ptr <= wr_ptr + 1; count <= count + 1; end
            if (rd_en && !empty) begin dout <= mem[rd_ptr]; rd_ptr <= rd_ptr + 1; count <= count - 1; end
        end
    end
endmodule

// SEL: stochastic selector — gates input bitstream with control stream
module sel_unit (
    input  sel, a,
    output y
);
    assign y = sel & a;
endmodule
