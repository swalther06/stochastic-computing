// HA: half adder
module ha (
    input  a, b,
    output sum, cout
);
    assign sum  = a ^ b;
    assign cout = a & b;
endmodule

// BIN_CONV: serial skew-to-binary converter — counts 1s in incoming skew stream
module bin_conv #(parameter A = 4) (
    input              clk, rst, skew_in,
    output reg [A-1:0] bin_out
);
    always_ff @(posedge clk) begin
        if (rst) bin_out <= 0;
        else if (skew_in) bin_out <= bin_out + 1;
    end
endmodule
