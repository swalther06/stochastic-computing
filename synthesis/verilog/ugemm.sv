
// PC: parallel counter — popcount of K 1-bit inputs
module pc #(parameter K = 4) (
    input  [K-1:0]           bits,
    output [$clog2(K+1)-1:0] count
);
    assign count = $countones(bits);
endmodule

// ACC: accumulator — integrates K-bit values over time
module acc #(parameter W = 8) (
    input              clk, rst,
    input  [W-1:0]     in,
    output reg [W-1:0] sum
);
    always_ff @(posedge clk or posedge rst) begin
        if (rst) sum <= 0;
        else     sum <= sum + in;
    end
endmodule

// MIN: minimum selector
module min_unit #(parameter W = 8) (
    input  [W-1:0] a, b,
    output [W-1:0] y
);
    assign y = (a < b) ? a : b;
endmodule
